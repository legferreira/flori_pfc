from datetime import datetime, timedelta, timezone as dt_timezone
import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from flori_backend.api import momento_exibicao, momento_iso
from .models import LogAtividade, Token, TrocaEmailPendente
from .services import ExcluirConta
from .tests_conta import SENHA, criar_usuario

EMAIL_NOVO = 'nova.ana@exemplo.com'


@patch('users.services.NotificacaoService')
class TrocaEmailTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.token = Token.objects.create(usuario=self.usuario)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {self.token.chave}'}

    def pedir(self, email=EMAIL_NOVO, senha=SENHA, auth=None):
        return self.client.post(
            '/api/perfil/email', {'email_novo': email, 'senha': senha},
            content_type='application/json', **(auth or self.auth),
        )

    def confirmar(self, codigo):
        return self.client.post(
            '/api/perfil/email/confirmar', {'codigo': codigo}, content_type='application/json', **self.auth,
        )

    def codigo_enviado(self, notificacao):
        return notificacao.return_value.enviar_codigo_troca_email.call_args.args[2]

    def codigo_errado(self, certo):
        return '000000' if certo != '000000' else '111111'

    def acoes(self):
        return list(LogAtividade.objects.filter(usuario=self.usuario).order_by('criado_em').values_list('acao', flat=True))

    def test_troca_completa(self, notificacao):
        outra_sessao = Token.objects.create(usuario=self.usuario)

        resposta = self.pedir('Nova.Ana@Exemplo.com')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(notificacao.return_value.enviar_codigo_troca_email.call_args.args[0], EMAIL_NOVO)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, 'ana@exemplo.com')

        confirmado = self.confirmar(self.codigo_enviado(notificacao))

        self.assertEqual(confirmado.status_code, 200)
        self.assertEqual(confirmado.json()['email'], EMAIL_NOVO)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, EMAIL_NOVO)
        self.assertFalse(TrocaEmailPendente.objects.exists())
        self.assertTrue(Token.objects.filter(pk=self.token.pk).exists())
        self.assertFalse(Token.objects.filter(pk=outra_sessao.pk).exists())
        notificacao.return_value.enviar_aviso_email_alterado.assert_called_once_with('ana@exemplo.com', 'ana', 'no****@exemplo.com')
        self.assertEqual(
            self.client.post('/api/login', {'contato': EMAIL_NOVO, 'senha': SENHA}, content_type='application/json').status_code,
            200,
        )

    def test_logs_sem_codigo_nem_email_completo(self, notificacao):
        self.pedir()
        codigo = self.codigo_enviado(notificacao)
        self.confirmar(self.codigo_errado(codigo))
        self.confirmar(codigo)

        self.assertEqual(self.acoes(), [
            'email_alteracao_solicitada', 'email_alteracao_codigo_invalido', 'email_alterado',
        ])
        texto = json.dumps(list(LogAtividade.objects.values('resumo', 'alvo_id')))
        for proibido in (codigo, EMAIL_NOVO, 'ana@exemplo.com'):
            self.assertNotIn(proibido, texto)
        alterado = LogAtividade.objects.get(acao=LogAtividade.Acao.EMAIL_ALTERADO)
        self.assertEqual(alterado.resumo, {'antes': 'an****@exemplo.com', 'depois': 'no****@exemplo.com'})

    def test_senha_errada(self, notificacao):
        self.assertEqual(self.pedir(senha='errada-000').status_code, 403)
        self.assertFalse(TrocaEmailPendente.objects.exists())
        log = LogAtividade.objects.get(acao=LogAtividade.Acao.EMAIL_ALTERACAO_RECUSADA)
        self.assertEqual(log.resumo, {'motivo': 'senha_incorreta'})

    def test_conta_google_bloqueada(self, notificacao):
        google = criar_usuario('google@exemplo.com', senha=None)
        auth = {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=google).chave}'}
        resposta = self.pedir(auth=auth)
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.json()['mensagem'], 'Contas que entram com Google não podem trocar o email por aqui.')
        self.assertEqual(LogAtividade.objects.get(usuario=google).resumo, {'motivo': 'conta_google'})

    def test_email_em_uso_responde_igual_ao_sucesso(self, notificacao):
        criar_usuario('ocupado@exemplo.com')
        em_uso = self.pedir('ocupado@exemplo.com')
        notificacao.return_value.enviar_codigo_troca_email.assert_not_called()
        self.assertFalse(TrocaEmailPendente.objects.exists())
        log = LogAtividade.objects.get(acao=LogAtividade.Acao.EMAIL_ALTERACAO_RECUSADA)
        self.assertEqual(log.resumo['motivo'], 'email_em_uso')
        self.assertNotIn('ocupado@exemplo.com', json.dumps(log.resumo))

        livre = self.pedir('livre@exemplo.com')
        self.assertEqual(em_uso.status_code, livre.status_code)
        self.assertEqual(em_uso.json()['mensagem'], livre.json()['mensagem'])
        self.assertEqual(set(em_uso.json()), set(livre.json()))

    def test_falha_no_aviso_ao_email_antigo_fica_registrada(self, notificacao):
        notificacao.return_value.enviar_aviso_email_alterado.side_effect = Exception('Brevo fora')
        self.pedir()

        self.assertEqual(self.confirmar(self.codigo_enviado(notificacao)).status_code, 200)

        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, EMAIL_NOVO)
        log = LogAtividade.objects.get(acao=LogAtividade.Acao.EMAIL_ALTERADO_AVISO_FALHOU)
        self.assertEqual(log.usuario, self.usuario)
        self.assertEqual(log.resumo, {'destino': 'an****@exemplo.com'})
        self.assertNotIn('ana@exemplo.com', json.dumps(log.resumo))

    def test_codigo_errado_permite_tentar_de_novo(self, notificacao):
        self.pedir()
        codigo = self.codigo_enviado(notificacao)
        self.assertEqual(self.confirmar(self.codigo_errado(codigo)).status_code, 400)
        self.assertEqual(self.confirmar(codigo).status_code, 200)

    def test_excesso_de_tentativas_invalida_a_troca(self, notificacao):
        self.pedir()
        codigo = self.codigo_enviado(notificacao)
        for _ in range(4):
            self.assertEqual(self.confirmar(self.codigo_errado(codigo)).status_code, 400)
        self.assertEqual(self.confirmar(self.codigo_errado(codigo)).status_code, 410)
        self.assertFalse(TrocaEmailPendente.objects.exists())
        self.assertEqual(self.confirmar(codigo).status_code, 410)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, 'ana@exemplo.com')

    def test_codigo_expirado(self, notificacao):
        self.pedir()
        TrocaEmailPendente.objects.update(expira_em=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.confirmar(self.codigo_enviado(notificacao)).status_code, 410)
        self.assertFalse(TrocaEmailPendente.objects.exists())
        self.assertTrue(LogAtividade.objects.filter(acao=LogAtividade.Acao.EMAIL_ALTERACAO_EXPIRADA).exists())

    def test_nova_solicitacao_substitui_a_anterior(self, notificacao):
        self.pedir('primeiro@exemplo.com')
        primeiro = self.codigo_enviado(notificacao)
        self.pedir('segundo@exemplo.com')
        self.assertEqual(TrocaEmailPendente.objects.get().email_novo, 'segundo@exemplo.com')
        if primeiro != self.codigo_enviado(notificacao):
            self.assertEqual(self.confirmar(primeiro).status_code, 400)

    def test_limite_de_3_por_hora(self, notificacao):
        for i in range(3):
            self.assertEqual(self.pedir(f'novo{i}@exemplo.com').status_code, 200)
        self.assertEqual(self.pedir('novo9@exemplo.com').status_code, 429)
        self.assertEqual(
            LogAtividade.objects.filter(acao=LogAtividade.Acao.EMAIL_ALTERACAO_RECUSADA).get().resumo,
            {'motivo': 'limite_excedido'},
        )

    def test_email_ocupado_depois_do_pedido_recusa_na_confirmacao(self, notificacao):
        self.pedir()
        criar_usuario(EMAIL_NOVO)
        self.assertEqual(self.confirmar(self.codigo_enviado(notificacao)).status_code, 409)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, 'ana@exemplo.com')

    def test_formato_invalido(self, notificacao):
        self.assertEqual(self.pedir('nao-e-email').status_code, 400)
        self.assertEqual(self.pedir('ana@exemplo.com').status_code, 400)

    def test_patch_continua_ignorando_email_e_nascimento(self, notificacao):
        self.client.patch(
            '/api/perfil', {'email': 'x@exemplo.com', 'data_nascimento': '01/01/2000'},
            content_type='application/json', **self.auth,
        )
        self.usuario.refresh_from_db()
        self.assertEqual((self.usuario.email, self.usuario.data_nascimento), ('ana@exemplo.com', '10/04/1995'))

    def test_exclusao_de_conta_apaga_troca_pendente(self, notificacao):
        self.pedir()
        ExcluirConta(self.usuario.id).executar()
        self.assertFalse(TrocaEmailPendente.objects.exists())


class DataEHoraNosLogsTests(TestCase):
    def test_log_guarda_data_e_hora_completas(self):
        momento = datetime(2026, 11, 12, 17, 5, 9, 123456, tzinfo=dt_timezone.utc)
        log = LogAtividade.objects.create(acao=LogAtividade.Acao.LOGIN_SUCESSO, criado_em=momento)
        log.refresh_from_db()
        automatico = LogAtividade.objects.create(acao=LogAtividade.Acao.LOGOUT)
        automatico.refresh_from_db()
        self.assertLess(abs(automatico.criado_em - timezone.now()), timedelta(seconds=5))
        self.assertIsNotNone(automatico.criado_em.tzinfo)
        self.assertEqual(log.criado_em, momento)
        self.assertEqual(momento_iso(log.criado_em), '2026-11-12T14:05:09.123456-03:00')
        self.assertEqual(momento_exibicao(log.criado_em), '12/11/2026 14:05:09')
