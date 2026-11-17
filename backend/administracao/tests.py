from io import StringIO
from unittest.mock import patch

from django.contrib.admin.sites import site
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, TestCase
from django.utils import timezone

from trilha.models import Card, Certificado, ProgressoCard, TentativaQuiz
from users.models import AdminProtegido, LogAtividade, Token, Usuario
from users.services import ErroExclusao, ExcluirConta


def criar_usuario(email, perfil=Usuario.Perfil.USER, senha='senha-12345'):
    usuario = Usuario(
        nome='Ana', sobrenome='Souza', apelido=email.split('@')[0],
        data_nascimento='10/04/1995', email=email, perfil=perfil,
    )
    usuario.definir_senha(senha)
    usuario.save()
    return usuario


def cabecalho(usuario):
    return {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=usuario).chave}'}


class BaseAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('carregar_trilha', verbosity=0)

    def setUp(self):
        patcher = patch('administracao.services.NotificacaoService')
        self.notificacao = patcher.start()
        self.addCleanup(patcher.stop)
        self.admin = criar_usuario('admin@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        self.comum = criar_usuario('comum@exemplo.com')
        self.auth_admin = cabecalho(self.admin)
        self.auth_comum = cabecalho(self.comum)

    def chamar(self, metodo, url, auth=None, dados=None):
        extra = auth if auth is not None else self.auth_admin
        return getattr(self.client, metodo)(url, dados or {}, content_type='application/json', **extra)

    def rotas(self):
        card = Card.objects.first()
        return [
            ('get', '/api/admin/dashboard'),
            ('get', '/api/admin/users'),
            ('post', f'/api/admin/users/{self.comum.id}/excluir'),
            ('get', '/api/admin/conteudo/cards'),
            ('post', '/api/admin/conteudo/cards'),
            ('get', f'/api/admin/conteudo/cards/{card.id}'),
            ('put', f'/api/admin/conteudo/cards/{card.id}'),
            ('post', f'/api/admin/conteudo/cards/{card.id}/excluir'),
            ('get', f'/api/admin/conteudo/cards/{card.id}/impacto'),
            ('get', '/api/admin/conteudo/quiz/resumo'),
        ]

    def logs(self, acao):
        return LogAtividade.objects.filter(acao=acao)


class AutorizacaoAdminTests(BaseAdminTests):
    def test_user_comum_recebe_403_em_todas_as_rotas_admin(self):
        for metodo, url in self.rotas():
            resposta = self.chamar(metodo, url, auth=self.auth_comum, dados={'motivo': 'conta_teste'})
            self.assertEqual(resposta.status_code, 403, f'{metodo} {url}')
        self.assertEqual(self.logs(LogAtividade.Acao.ADMIN_ACESSO_NEGADO).count(), len(self.rotas()))
        self.assertTrue(Usuario.objects.filter(pk=self.comum.pk).exists())

    def test_sem_token_recebe_401(self):
        for metodo, url in self.rotas():
            self.assertEqual(self.chamar(metodo, url, auth={}).status_code, 401, f'{metodo} {url}')

    def test_admin_acessa(self):
        self.assertEqual(self.chamar('get', '/api/admin/dashboard').status_code, 200)


class AdminIndelevelTests(BaseAdminTests):
    def test_servico_de_exclusao_recusa_admin(self):
        with self.assertRaises(ErroExclusao):
            ExcluirConta(self.admin.id).executar()
        self.assertTrue(Usuario.objects.filter(pk=self.admin.pk).exists())

    def test_rota_admin_nao_exclui_outro_admin(self):
        outro = criar_usuario('outro@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        resposta = self.chamar('post', f'/api/admin/users/{outro.id}/excluir', dados={'motivo': 'conta_teste'})
        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Usuario.objects.filter(pk=outro.pk).exists())

    def test_delete_do_model_e_do_queryset_bloqueados(self):
        with self.assertRaises(AdminProtegido):
            self.admin.delete()
        with self.assertRaises(AdminProtegido):
            Usuario.objects.all().delete()
        self.assertEqual(Usuario.objects.count(), 2)

    def test_ultimo_admin_nao_pode_ser_rebaixado(self):
        self.admin.perfil = Usuario.Perfil.USER
        with self.assertRaises(AdminProtegido):
            self.admin.save()
        outro = criar_usuario('outro@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        outro.perfil = Usuario.Perfil.USER
        outro.save()
        self.assertEqual(Usuario.objects.admins().count(), 1)

    def test_trigger_do_mysql_bloqueia_delete_direto(self):
        if connection.vendor != 'mysql':
            self.skipTest('Trigger só existe no MySQL.')
        sem_vinculos = criar_usuario('solta@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        with self.assertRaises(DatabaseError) as erro:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('DELETE FROM users WHERE id = %s', [sem_vinculos.id.hex])
        self.assertIn('admin', str(erro.exception))
        self.assertTrue(Usuario.objects.filter(pk=sem_vinculos.pk).exists())

        comum = criar_usuario('sem_vinculo@exemplo.com')
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM users WHERE id = %s', [comum.id.hex])
        self.assertFalse(Usuario.objects.filter(pk=comum.pk).exists())

    def test_django_admin_sem_exclusao_de_usuario(self):
        requisicao = RequestFactory().get('/admin/')
        model_admin = site._registry[Usuario]
        self.assertFalse(model_admin.has_delete_permission(requisicao))
        requisicao.user = type('Staff', (), {'has_perm': lambda *a: True, 'is_active': True, 'is_staff': True})()
        self.assertNotIn('delete_selected', model_admin.get_actions(requisicao))


class AuditoriaAdminTests(BaseAdminTests):
    def test_cada_acao_admin_gera_log(self):
        self.chamar('get', '/api/admin/dashboard')
        self.chamar('get', '/api/admin/users')
        guia = self.chamar('post', '/api/admin/conteudo/guias', dados={'titulo': 'OMS', 'passos': ['Respire']}).json()
        self.chamar('put', f'/api/admin/conteudo/guias/{guia["id"]}', dados={
            'titulo': 'OMS 2', 'passos': ['Respire'], 'atualizado_em': guia['atualizado_em'],
        })
        self.chamar('post', f'/api/admin/conteudo/guias/{guia["id"]}/desativar')
        self.chamar('post', f'/api/admin/users/{self.comum.id}/excluir', dados={'motivo': 'pedido_titular', 'observacao': 'pedido pelo canal'})

        for acao in (
            LogAtividade.Acao.ADMIN_CONSULTOU_DASHBOARD, LogAtividade.Acao.ADMIN_LISTOU_USUARIOS,
            LogAtividade.Acao.ADMIN_CONTEUDO_CRIADO,
            LogAtividade.Acao.ADMIN_CONTEUDO_EDITADO, LogAtividade.Acao.ADMIN_CONTEUDO_DESATIVADO,
            LogAtividade.Acao.ADMIN_USER_EXCLUIDO,
        ):
            log = self.logs(acao).get()
            self.assertEqual(log.ator, self.admin, acao)

        exclusao = self.logs(LogAtividade.Acao.ADMIN_USER_EXCLUIDO).get()
        self.assertEqual(exclusao.resumo, {'motivo': 'pedido_titular'})
        self.assertNotIn('comum@exemplo.com', str(exclusao.resumo) + exclusao.alvo_id)
        edicao = self.logs(LogAtividade.Acao.ADMIN_CONTEUDO_EDITADO).get()
        self.assertEqual(edicao.alvo_tipo, 'guia')
        self.assertEqual(edicao.resumo, {'campos': ['titulo'], 'antes': {'titulo': 'OMS'}, 'depois': {'titulo': 'OMS 2'}})

    def test_rota_de_logs_nao_existe_mais_e_logs_continuam_gravados(self):
        self.assertEqual(self.chamar('get', '/api/admin/logs').status_code, 404)
        self.assertFalse(self.logs(LogAtividade.Acao.ADMIN_CONSULTOU_LOGS).exists())
        self.chamar('get', '/api/admin/dashboard')
        self.assertEqual(self.logs(LogAtividade.Acao.ADMIN_CONSULTOU_DASHBOARD).count(), 1)

    def test_logs_antigos_de_consulta_continuam_no_banco(self):
        antigo = LogAtividade.objects.create(
            usuario=self.admin, ator=self.admin, acao=LogAtividade.Acao.ADMIN_CONSULTOU_LOGS, alvo_tipo='log',
        )
        self.chamar('get', '/api/admin/dashboard')
        antigo.refresh_from_db()
        self.assertEqual(antigo.get_acao_display(), 'Admin consultou os logs')


class LimparProgressoAdminTests(BaseAdminTests):
    def preparar(self, usuario, codigo):
        trilha = Card.objects.first().assunto.trilha
        for card in Card.objects.all():
            ProgressoCard.objects.create(usuario=usuario, card=card)
        tentativa = TentativaQuiz.objects.create(
            usuario=usuario, trilha=trilha, acertos=10, total_perguntas=10, percentual=100, aprovada=True,
            finalizada_em=timezone.now(),
        )
        TentativaQuiz.objects.create(
            usuario=usuario, trilha=trilha, acertos=5, total_perguntas=10, percentual=50, aprovada=False,
            finalizada_em=timezone.now(),
        )
        Certificado.objects.create(
            usuario=usuario, trilha=trilha, tentativa=tentativa, codigo=codigo, nome_completo='Ana Souza',
        )

    def rodar(self):
        saida = StringIO()
        call_command('limpar_progresso_admin', stdout=saida)
        return saida.getvalue()

    def test_apaga_so_registros_de_admin_e_registra_log(self):
        self.preparar(self.admin, 'FLORI-ADMN-0001')
        self.preparar(self.comum, 'FLORI-USER-0001')
        self.rodar()

        for modelo in (ProgressoCard, TentativaQuiz, Certificado):
            self.assertFalse(modelo.objects.filter(usuario=self.admin).exists(), modelo.__name__)
        self.assertEqual(ProgressoCard.objects.filter(usuario=self.comum).count(), Card.objects.count())
        self.assertEqual(TentativaQuiz.objects.filter(usuario=self.comum).count(), 2)
        self.assertTrue(Certificado.objects.filter(usuario=self.comum).exists())
        log = self.logs(LogAtividade.Acao.PROGRESSO_ADMIN_LIMPO).get()
        self.assertEqual(log.resumo, {
            'contas_admin': 1, 'certificados': 1, 'tentativas_quiz': 2, 'progresso_cards': Card.objects.count(),
        })

    def test_rodar_de_novo_nao_muda_nada(self):
        self.preparar(self.admin, 'FLORI-ADMN-0001')
        self.rodar()
        self.assertIn('nada foi apagado', self.rodar())
        self.assertEqual(self.logs(LogAtividade.Acao.PROGRESSO_ADMIN_LIMPO).count(), 1)


class CertificadoComUsuarioExcluidoTests(BaseAdminTests):
    def test_admin_exclui_user_com_certificado(self):
        for card in Card.objects.all():
            ProgressoCard.objects.create(usuario=self.comum, card=card)
        tentativa = TentativaQuiz.objects.create(
            usuario=self.comum, trilha=Card.objects.first().assunto.trilha, acertos=10, total_perguntas=10,
            percentual=100, aprovada=True, finalizada_em=timezone.now(),
        )
        Certificado.objects.create(
            usuario=self.comum, trilha=tentativa.trilha, tentativa=tentativa, codigo='FLORI-TEST-0001',
            nome_completo='Ana Souza',
        )
        resposta = self.chamar('post', f'/api/admin/users/{self.comum.id}/excluir', dados={'motivo': 'conta_teste'})
        self.assertEqual(resposta.status_code, 204)
        self.assertFalse(Certificado.objects.exists())
        self.assertFalse(Usuario.objects.get(pk=self.comum.pk).ativo)


class AvisoDeExclusaoPeloAdminTests(BaseAdminTests):
    def excluir(self):
        return self.chamar('post', f'/api/admin/users/{self.comum.id}/excluir', dados={'motivo': 'pedido_titular', 'observacao': 'pedido pelo canal'})

    def test_avisa_a_pessoa_excluida(self):
        self.assertEqual(self.excluir().status_code, 204)
        self.notificacao.return_value.enviar_conta_excluida.assert_called_once_with(
            'comum@exemplo.com', 'comum', pelo_admin=True,
        )
        self.assertFalse(LogAtividade.objects.filter(acao=LogAtividade.Acao.EXCLUSAO_AVISO_FALHOU).exists())

    def test_falha_no_aviso_fica_registrada_sem_o_email_completo(self):
        self.notificacao.return_value.enviar_conta_excluida.side_effect = Exception('Brevo fora')
        usuario_id = self.comum.id

        self.assertEqual(self.excluir().status_code, 204)

        self.assertFalse(Usuario.objects.get(pk=usuario_id).ativo)
        log = LogAtividade.objects.get(acao=LogAtividade.Acao.EXCLUSAO_AVISO_FALHOU)
        self.assertEqual(log.usuario_id, usuario_id)
        self.assertEqual(log.ator, self.admin)
        self.assertEqual(log.alvo_id, str(usuario_id))
        self.assertEqual(log.resumo, {'destino': 'co****@exemplo.com'})
        self.assertNotIn('comum@exemplo.com', str(log.resumo) + log.alvo_id)
