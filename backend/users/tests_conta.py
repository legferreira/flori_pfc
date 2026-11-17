from datetime import timedelta
from io import StringIO
import os
from unittest.mock import patch

from django.contrib.admin.sites import site
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from trilha.models import Card, Certificado, ProgressoCard, TentativaQuiz

from .auditoria import registrar_log_admin
from .models import (
    CodigoAutenticacao, Consentimento, LogAtividade, LogImutavel,
    SolicitacaoRedefinicaoSenha, TentativaLogin, Token, Usuario,
)
from .services import VERSAO_POLITICA_PRIVACIDADE, VERSAO_TERMOS_USO, ExcluirConta

SENHA = 'senha-12345'


def criar_usuario(email='ana@exemplo.com', perfil=Usuario.Perfil.USER, senha=SENHA, **extra):
    usuario = Usuario(
        nome='Ana', sobrenome='Souza', apelido='ana', data_nascimento='10/04/1995',
        email=email, perfil=perfil, **extra,
    )
    if senha:
        usuario.definir_senha(senha)
    else:
        usuario.definir_sem_senha()
    usuario.save()
    for tipo in Consentimento.DOCUMENTOS:
        Consentimento.objects.create(usuario=usuario, tipo=tipo, versao_documento='1.0', aceito=True)
    return usuario


class BaseContaTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.token = Token.objects.create(usuario=self.usuario)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {self.token.chave}'}

    def excluir(self, dados, auth=None):
        return self.client.delete(
            '/api/perfil/conta', dados, content_type='application/json', **(auth or self.auth),
        )


@patch('users.services.NotificacaoService')
class ExclusaoDeContaTests(BaseContaTests):
    def preparar_dados(self):
        call_command('carregar_trilha', verbosity=0)
        for card in Card.objects.all():
            ProgressoCard.objects.create(usuario=self.usuario, card=card)
        tentativa = TentativaQuiz.objects.create(
            usuario=self.usuario, trilha=Card.objects.first().assunto.trilha, acertos=9, total_perguntas=10,
            percentual=90, aprovada=True, finalizada_em=timezone.now(),
        )
        Certificado.objects.create(
            usuario=self.usuario, trilha=tentativa.trilha, tentativa=tentativa,
            codigo='FLORI-ABCD-EFGH', nome_completo='Ana Souza',
        )
        CodigoAutenticacao.objects.create(
            usuario=self.usuario, desafio_hash='x' * 64, codigo_hash='y',
            expira_em=timezone.now() + timedelta(minutes=5),
        )
        SolicitacaoRedefinicaoSenha.objects.create(email=self.usuario.email, usuario=self.usuario)
        LogAtividade.objects.create(usuario=self.usuario, acao=LogAtividade.Acao.LOGIN_SUCESSO)

    def test_exclui_vinculos_e_anonimiza_sem_apagar_a_linha(self, notificacao):
        self.preparar_dados()
        usuario_id = self.usuario.id

        resposta = self.excluir({'senha': SENHA, 'confirmacao': 'EXCLUIR'})

        self.assertEqual(resposta.status_code, 204)
        excluido = Usuario.objects.get(pk=usuario_id)
        self.assertFalse(excluido.ativo)
        self.assertIsNotNone(excluido.excluido_em)
        for model in (Token, CodigoAutenticacao, ProgressoCard, TentativaQuiz, Certificado):
            self.assertFalse(model.objects.exists(), model.__name__)
        self.assertFalse(SolicitacaoRedefinicaoSenha.objects.filter(email='ana@exemplo.com').exists())
        self.assertEqual(Consentimento.objects.filter(usuario_id=usuario_id).count(), 2)

        self.assertTrue(LogAtividade.objects.filter(acao=LogAtividade.Acao.LOGIN_SUCESSO, usuario_id=usuario_id).exists())
        log = LogAtividade.objects.get(acao=LogAtividade.Acao.EXCLUSAO_CONTA_PROPRIA)
        self.assertEqual(log.alvo_id, str(usuario_id))
        self.assertEqual(log.usuario_id, usuario_id)
        self.assertNotIn('ana@exemplo.com', str(log.resumo))

        notificacao.return_value.enviar_conta_excluida.assert_called_once_with('ana@exemplo.com', 'ana')
        self.assertEqual(self.client.get('/api/perfil', **self.auth).status_code, 401)

    def test_senha_errada_recusa_e_registra(self, notificacao):
        resposta = self.excluir({'senha': 'errada-123', 'confirmacao': 'EXCLUIR'})
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Usuario.objects.filter(pk=self.usuario.pk).exists())
        self.assertTrue(LogAtividade.objects.filter(
            usuario=self.usuario, acao=LogAtividade.Acao.EXCLUSAO_CONTA_RECUSADA,
        ).exists())
        notificacao.return_value.enviar_conta_excluida.assert_not_called()

    def test_exige_texto_de_confirmacao(self, notificacao):
        self.assertEqual(self.excluir({'senha': SENHA, 'confirmacao': 'excluir'}).status_code, 400)
        self.assertTrue(Usuario.objects.filter(pk=self.usuario.pk).exists())

    def test_bloqueia_depois_de_varias_recusas(self, notificacao):
        for _ in range(5):
            self.excluir({'senha': 'errada-123', 'confirmacao': 'EXCLUIR'})
        self.assertEqual(self.excluir({'senha': SENHA, 'confirmacao': 'EXCLUIR'}).status_code, 429)

    def test_conta_google_exige_codigo_por_email(self, notificacao):
        google = criar_usuario('google@exemplo.com', senha=None)
        auth = {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=google).chave}'}

        sem_codigo = self.excluir({'confirmacao': 'EXCLUIR'}, auth=auth)
        self.assertEqual(sem_codigo.status_code, 400)

        desafio = self.client.post('/api/perfil/conta/codigo', **auth).json()['desafio']
        codigo = notificacao.return_value.enviar_codigo_exclusao.call_args.args[1]
        errado = '000000' if codigo != '000000' else '111111'
        self.assertEqual(self.excluir({'confirmacao': 'EXCLUIR', 'desafio': desafio, 'codigo': errado}, auth=auth).status_code, 403)
        certo = self.excluir({'confirmacao': 'EXCLUIR', 'desafio': desafio, 'codigo': codigo}, auth=auth)
        self.assertEqual(certo.status_code, 204)
        google.refresh_from_db()
        self.assertFalse(google.ativo)

    def test_conta_com_senha_nao_pede_codigo(self, notificacao):
        self.assertEqual(self.client.post('/api/perfil/conta/codigo', **self.auth).status_code, 400)

    def test_exclusao_e_idempotente(self, notificacao):
        ExcluirConta(self.usuario.id).executar()
        self.assertIsNone(ExcluirConta(self.usuario.id).executar())
        self.assertEqual(LogAtividade.objects.filter(acao=LogAtividade.Acao.EXCLUSAO_CONTA_PROPRIA).count(), 1)
        self.assertEqual(Consentimento.objects.filter(usuario=self.usuario).count(), 2)

    def test_admin_nao_ve_exclusao_propria(self, notificacao):
        admin = criar_usuario('admin@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        auth = {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=admin).chave}'}
        self.assertEqual(self.excluir({'senha': SENHA, 'confirmacao': 'EXCLUIR'}, auth=auth).status_code, 403)
        self.assertTrue(Usuario.objects.filter(pk=admin.pk).exists())


class PerfilEExportacaoTests(BaseContaTests):
    def test_patch_ignora_campo_perfil(self):
        resposta = self.client.patch(
            '/api/perfil', {'perfil': 'admin', 'apelido': 'aninha'}, content_type='application/json', **self.auth,
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['perfil'], 'user')
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.perfil, Usuario.Perfil.USER)
        log = LogAtividade.objects.get(acao=LogAtividade.Acao.PERFIL_ATUALIZADO)
        self.assertEqual(log.resumo, {'campos': ['apelido']})

    def test_log_de_celular_nao_guarda_o_numero(self):
        self.client.patch('/api/perfil', {'celular': '(11) 91234-5678'}, content_type='application/json', **self.auth)
        log = LogAtividade.objects.get(acao=LogAtividade.Acao.PERFIL_ATUALIZADO)
        self.assertEqual(log.resumo['campos'], ['celular'])
        self.assertNotIn('91234', str(log.resumo))

    def test_revogar_consentimento_gera_log(self):
        self.client.post(
            '/api/perfil/consentimentos', {'tipo': 'termos_uso', 'aceito': False},
            content_type='application/json', **self.auth,
        )
        self.assertTrue(LogAtividade.objects.filter(acao=LogAtividade.Acao.CONSENTIMENTO_REVOGADO).exists())

    def test_exportacao_sem_senha_nem_tokens(self):
        resposta = self.client.get('/api/perfil/exportacao', **self.auth)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('attachment', resposta['Content-Disposition'])
        texto = resposta.content.decode()
        self.assertNotIn('senha_hash', texto)
        self.assertNotIn(self.usuario.senha_hash, texto)
        self.assertNotIn(self.token.chave, texto)
        dados = resposta.json()
        self.assertEqual(dados['perfil']['email'], 'ana@exemplo.com')
        self.assertEqual(len(dados['consentimentos']['historico']), 2)
        self.assertTrue(LogAtividade.objects.filter(acao=LogAtividade.Acao.EXPORTACAO_DADOS).exists())

    def test_exportacao_limitada_a_5_por_hora(self):
        for _ in range(5):
            self.assertEqual(self.client.get('/api/perfil/exportacao', **self.auth).status_code, 200)
        self.assertEqual(self.client.get('/api/perfil/exportacao', **self.auth).status_code, 429)


class LogImutavelTests(TestCase):
    def setUp(self):
        self.admin = criar_usuario('admin@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        self.log = registrar_log_admin(self.admin, LogAtividade.Acao.ADMIN_CONSULTOU_DASHBOARD, 'dashboard')
        self.comum = LogAtividade.objects.create(acao=LogAtividade.Acao.LOGIN_SUCESSO)

    def test_nenhum_log_pode_ser_alterado(self):
        for log in (self.log, self.comum):
            log.alvo_tipo = 'outro'
            with self.assertRaises(LogImutavel):
                log.save()
            with self.assertRaises(LogImutavel):
                LogAtividade.objects.filter(pk=log.pk).update(alvo_tipo='outro')

    def test_nenhum_log_pode_ser_apagado(self):
        for log in (self.log, self.comum):
            with self.assertRaises(LogImutavel):
                log.delete()
        with self.assertRaises(LogImutavel):
            LogAtividade.objects.comuns().delete()
        with self.assertRaises(LogImutavel):
            LogAtividade.objects.all().delete()
        self.assertEqual(LogAtividade.objects.count(), 2)

    def test_trigger_do_mysql_bloqueia_delete_direto(self):
        if connection.vendor != 'mysql':
            self.skipTest('Trigger só existe no MySQL.')
        with self.assertRaises(DatabaseError) as erro:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('DELETE FROM logs_atividade WHERE id = %s', [self.comum.id.hex])
        self.assertIn('Logs de atividade', str(erro.exception))
        self.assertTrue(LogAtividade.objects.filter(pk=self.comum.pk).exists())

    def test_django_admin_somente_leitura(self):
        model_admin = site._registry[LogAtividade]
        requisicao = RequestFactory().get('/admin/')
        self.assertFalse(model_admin.has_add_permission(requisicao))
        self.assertFalse(model_admin.has_change_permission(requisicao, self.log))
        self.assertFalse(model_admin.has_delete_permission(requisicao, self.log))

    def test_resumo_descarta_dados_sensiveis(self):
        log = registrar_log_admin(
            self.admin, LogAtividade.Acao.ADMIN_EDITOU_CONTEUDO, 'card', '1',
            {'senha': 'x', 'token': 'y', 'email': 'a@b.com', 'codigo_2fa': '123456', 'tema': 'ok'},
        )
        self.assertEqual(log.resumo, {'tema': 'ok'})


@patch('users.services.NotificacaoService')
class LoginAdminTests(TestCase):
    def setUp(self):
        self.admin = criar_usuario('admin@exemplo.com', perfil=Usuario.Perfil.ADMIN)

    def login(self, senha=SENHA):
        return self.client.post(
            '/api/login', {'contato': 'admin@exemplo.com', 'senha': senha}, content_type='application/json',
        )

    def test_admin_sempre_passa_pelo_codigo(self, notificacao):
        resposta = self.login()
        self.assertTrue(resposta.json()['requer_codigo'])
        codigo = notificacao.return_value.enviar_codigo_autenticacao.call_args.args[1]
        verificado = self.client.post(
            '/api/login/verificar', {'desafio': resposta.json()['desafio'], 'codigo': codigo},
            content_type='application/json',
        )
        self.assertEqual(verificado.status_code, 200)
        log = LogAtividade.objects.get(acao=LogAtividade.Acao.ADMIN_LOGIN)
        self.assertEqual(log.ator, self.admin)

    @patch('google.oauth2.id_token.verify_firebase_token')
    def test_login_google_de_admin_pede_codigo(self, verificar, notificacao):
        verificar.return_value = {
            'email': 'admin@exemplo.com', 'email_verified': True, 'name': 'Ana Souza',
            'firebase': {'sign_in_provider': 'google.com'},
        }
        resposta = self.client.post('/api/login/google', {'id_token': 't'}, content_type='application/json')
        self.assertTrue(resposta.json()['requer_codigo'])
        self.assertNotIn('token', resposta.json())
        self.assertFalse(Token.objects.exists())

    def test_bloqueio_temporario_por_email(self, notificacao):
        for _ in range(5):
            self.assertEqual(self.login('errada-000').status_code, 401)
        self.assertEqual(self.login().status_code, 429)
        self.assertEqual(TentativaLogin.objects.count(), 5)
        notificacao.return_value.enviar_codigo_autenticacao.assert_not_called()

    def test_bloqueio_temporario_por_ip(self, notificacao):
        for i in range(20):
            self.client.post(
                '/api/login', {'contato': f'x{i}@exemplo.com', 'senha': 'errada-000'}, content_type='application/json',
            )
        self.assertEqual(self.login().status_code, 429)


class ComandosTests(TestCase):
    @patch.dict(os.environ, {'ADMIN_EMAIL': 'chefe@exemplo.com', 'ADMIN_NOME': 'Leti Ferreira', 'ADMIN_SENHA': 'senha-muito-forte'})
    def test_criar_admin_e_idempotente(self):
        call_command('criar_admin', stdout=StringIO())
        call_command('criar_admin', stdout=StringIO())
        admin = Usuario.objects.get(email='chefe@exemplo.com')
        self.assertEqual(admin.perfil, Usuario.Perfil.ADMIN)
        self.assertTrue(admin.verificar_senha('senha-muito-forte'))
        self.assertEqual((admin.nome, admin.sobrenome), ('Leti', 'Ferreira'))
        self.assertEqual(len(admin.consentimentos_atuais()), 2)
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(LogAtividade.objects.filter(acao=LogAtividade.Acao.ADMIN_CRIADO).count(), 2)

    @patch.dict(os.environ, {'ADMIN_EMAIL': 'ana@exemplo.com', 'ADMIN_NOME': '', 'ADMIN_SENHA': ''})
    def test_criar_admin_promove_conta_existente(self):
        usuario = criar_usuario()
        call_command('criar_admin', stdout=StringIO())
        usuario.refresh_from_db()
        self.assertEqual(usuario.perfil, Usuario.Perfil.ADMIN)
        self.assertTrue(usuario.verificar_senha(SENHA))

    @override_settings(LOG_RETENCAO_DIAS=365, LOG_RETENCAO_ADMIN_DIAS=1825)
    def test_anonimizar_logs_remove_so_o_ip_e_mantem_as_linhas(self):
        admin = criar_usuario('admin@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        agora = timezone.now()

        def log(acao, dias, ator=None):
            return LogAtividade.objects.create(
                acao=acao, ator=ator, usuario=ator, ip_origem='10.0.0.1', criado_em=agora - timedelta(days=dias),
            )

        comum_velho = log(LogAtividade.Acao.LOGIN_SUCESSO, 366)
        comum_novo = log(LogAtividade.Acao.LOGIN_SUCESSO, 364)
        admin_meio = log(LogAtividade.Acao.ADMIN_LOGIN, 400, admin)
        admin_velho = log(LogAtividade.Acao.ADMIN_LOGIN, 1826, admin)
        CodigoAutenticacao.objects.create(
            usuario=admin, desafio_hash='1' * 64, codigo_hash='x', expira_em=agora - timedelta(minutes=1),
        )
        valido = CodigoAutenticacao.objects.create(
            usuario=admin, desafio_hash='2' * 64, codigo_hash='x', expira_em=agora + timedelta(minutes=10),
        )
        total = LogAtividade.objects.count()

        call_command('anonimizar_logs', stdout=StringIO())

        self.assertEqual(LogAtividade.objects.count(), total)
        ips = dict(LogAtividade.objects.values_list('pk', 'ip_origem'))
        self.assertIsNone(ips[comum_velho.pk])
        self.assertEqual(ips[comum_novo.pk], '10.0.0.1')
        self.assertEqual(ips[admin_meio.pk], '10.0.0.1')
        self.assertIsNone(ips[admin_velho.pk])
        velho = LogAtividade.objects.get(pk=comum_velho.pk)
        self.assertEqual((velho.acao, velho.criado_em), (comum_velho.acao, comum_velho.criado_em))
        self.assertEqual(list(CodigoAutenticacao.objects.all()), [valido])

    @override_settings(DEBUG=True)
    def test_limpar_demo_sem_definitivo_so_exclui_logicamente(self):
        call_command('carregar_trilha', verbosity=0)
        real = criar_usuario('real@exemplo.com')
        disfarcado = criar_usuario('esperta@demo.flori.test')
        call_command('popular_demo', quantidade=8, stdout=StringIO())
        self.assertEqual(Usuario.objects.filter(demo=True, ativo=True).count(), 8)

        call_command('limpar_demo', stdout=StringIO())

        self.assertEqual(Usuario.objects.filter(demo=True, ativo=False).count(), 8)
        self.assertFalse(Usuario.objects.filter(demo=True, ativo=True).exists())
        self.assertTrue(Usuario.objects.get(pk=real.pk).ativo)
        self.assertTrue(Usuario.objects.get(pk=disfarcado.pk).ativo)
        self.assertEqual(LogAtividade.objects.filter(acao=LogAtividade.Acao.EXCLUSAO_CONTA_DEMO).count(), 8)

    @override_settings(DEBUG=True)
    def test_limpar_demo_definitivo_apaga_as_linhas_e_mantem_os_logs(self):
        call_command('carregar_trilha', verbosity=0)
        real = criar_usuario('real@exemplo.com')
        call_command('popular_demo', quantidade=5, stdout=StringIO())
        logs_antes = LogAtividade.objects.count()

        call_command('limpar_demo', definitivo=True, stdout=StringIO())

        self.assertFalse(Usuario.objects.filter(demo=True).exists())
        self.assertTrue(Usuario.objects.filter(pk=real.pk).exists())
        self.assertEqual(Consentimento.objects.filter(usuario=real).count(), 2)
        self.assertEqual(LogAtividade.objects.count(), logs_antes + 5)
        self.assertEqual(LogAtividade.objects.filter(acao=LogAtividade.Acao.EXCLUSAO_CONTA_DEMO, usuario__isnull=True).count(), 5)

    @override_settings(DEBUG=False)
    def test_demo_recusa_sem_debug(self):
        with self.assertRaises(CommandError):
            call_command('popular_demo')
        with self.assertRaises(CommandError):
            call_command('limpar_demo')


class VersaoDosDocumentosTests(BaseContaTests):
    def consentir(self, tipo, aceito):
        return self.client.post(
            '/api/perfil/consentimentos', {'tipo': tipo, 'aceito': aceito},
            content_type='application/json', **self.auth,
        )

    def test_reativacao_grava_a_versao_vigente(self):
        self.consentir('termos_uso', False)
        revogado = self.usuario.consentimentos_atuais()['termos_uso']
        self.assertEqual(revogado.versao_documento, '1.0')
        self.consentir('termos_uso', True)
        reativado = self.usuario.consentimentos_atuais()['termos_uso']
        self.assertTrue(reativado.aceito)
        self.assertEqual(reativado.versao_documento, VERSAO_TERMOS_USO)

    def test_perfil_aponta_documentos_desatualizados(self):
        corpo = self.client.get('/api/perfil', **self.auth).json()
        self.assertEqual(sorted(corpo['documentos_desatualizados']), ['politica_privacidade', 'termos_uso'])

        self.consentir('termos_uso', False)
        self.consentir('termos_uso', True)
        corpo = self.client.get('/api/perfil', **self.auth).json()
        self.assertEqual(corpo['documentos_desatualizados'], ['politica_privacidade'])

    def test_versao_vigente_nao_gera_aviso_nem_bloqueia(self):
        atual = criar_usuario('atual@exemplo.com')
        Consentimento.objects.filter(usuario=atual, tipo='termos_uso').update(versao_documento=VERSAO_TERMOS_USO)
        Consentimento.objects.filter(usuario=atual, tipo='politica_privacidade').update(
            versao_documento=VERSAO_POLITICA_PRIVACIDADE,
        )
        auth = {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=atual).chave}'}
        self.assertEqual(self.client.get('/api/perfil', **auth).json()['documentos_desatualizados'], [])
        self.assertEqual(self.client.get('/api/perfil', **self.auth).status_code, 200)


class AceitarDocumentosTests(BaseContaTests):
    URL = '/api/perfil/documentos/aceitar'

    def aceitar(self, auth=None):
        return self.client.post(self.URL, content_type='application/json', **(self.auth if auth is None else auth))

    def test_exige_autenticacao(self):
        self.assertEqual(self.aceitar(auth={}).status_code, 401)
        self.assertEqual(Consentimento.objects.count(), 2)

    def test_grava_nova_versao_mantem_historico_e_banner_some(self):
        antigos = list(Consentimento.objects.filter(usuario=self.usuario).values_list('pk', 'versao_documento'))

        resposta = self.aceitar()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['documentos_desatualizados'], [])
        self.assertEqual(self.client.get('/api/perfil', **self.auth).json()['documentos_desatualizados'], [])
        for pk, versao in antigos:
            self.assertEqual(Consentimento.objects.get(pk=pk).versao_documento, versao)
        novos = Consentimento.objects.filter(usuario=self.usuario).exclude(pk__in=[pk for pk, _ in antigos])
        self.assertEqual(
            sorted(novos.values_list('tipo', 'versao_documento', 'aceito')),
            [('politica_privacidade', VERSAO_POLITICA_PRIVACIDADE, True), ('termos_uso', VERSAO_TERMOS_USO, True)],
        )
        self.assertTrue(all(c.ip_origem == '127.0.0.1' and c.data_consentimento for c in novos))

    def test_cria_log_com_as_versoes(self):
        self.aceitar()
        log = LogAtividade.objects.get(acao=LogAtividade.Acao.DOCUMENTOS_ACEITOS)
        self.assertEqual(log.usuario, self.usuario)
        self.assertEqual(log.resumo, {'versoes': {
            'termos_uso': VERSAO_TERMOS_USO, 'politica_privacidade': VERSAO_POLITICA_PRIVACIDADE,
        }})

    def test_quem_ja_esta_atualizado_nao_duplica(self):
        self.aceitar()
        total = Consentimento.objects.count()
        resposta = self.aceitar()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Consentimento.objects.count(), total)
        self.assertEqual(LogAtividade.objects.filter(acao=LogAtividade.Acao.DOCUMENTOS_ACEITOS).count(), 1)

    def test_consentimento_revogado_nao_e_aceito_pelo_banner(self):
        self.client.post(
            '/api/perfil/consentimentos', {'tipo': 'termos_uso', 'aceito': False},
            content_type='application/json', **self.auth,
        )
        self.aceitar()
        atuais = self.usuario.consentimentos_atuais()
        self.assertFalse(atuais['termos_uso'].aceito)
        self.assertEqual(atuais['politica_privacidade'].versao_documento, VERSAO_POLITICA_PRIVACIDADE)


class IpDosConsentimentosTests(TestCase):
    @override_settings(CONSENTIMENTO_RETENCAO_DIAS=1825)
    def test_anonimizar_logs_remove_ip_do_consentimento_antigo_e_mantem_a_linha(self):
        usuario = criar_usuario()
        Consentimento.objects.filter(usuario=usuario).update(ip_origem='10.0.0.9')
        velho = Consentimento.objects.filter(usuario=usuario, tipo='termos_uso').first()
        Consentimento.objects.filter(pk=velho.pk).update(
            data_consentimento=timezone.now() - timedelta(days=1826),
        )
        total = Consentimento.objects.count()

        call_command('anonimizar_logs', stdout=StringIO())

        self.assertEqual(Consentimento.objects.count(), total)
        velho.refresh_from_db()
        self.assertIsNone(velho.ip_origem)
        self.assertTrue(velho.aceito)
        novo = Consentimento.objects.get(usuario=usuario, tipo='politica_privacidade')
        self.assertEqual(novo.ip_origem, '10.0.0.9')
