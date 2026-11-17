from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase, override_settings

from .models import Usuario
from .notificacoes import ErroNotificacao, NotificacaoService


@override_settings(
    BREVO_API_KEY='chave-de-teste', BREVO_REMETENTE_EMAIL='contato@flori.test', FRONTEND_URL='https://flori.test',
)
@patch('users.notificacoes.requests.post')
class NotificacaoServiceTests(SimpleTestCase):
    def setUp(self):
        self.usuario = Usuario(apelido='Bia', email='bia@exemplo.com')

    def payload(self, post):
        self.assertEqual(post.call_count, 1)
        argumentos = post.call_args
        self.assertEqual(argumentos.args[0], NotificacaoService.URL_ENVIO)
        self.assertEqual(argumentos.kwargs['headers']['api-key'], 'chave-de-teste')
        self.assertEqual(argumentos.kwargs['timeout'], NotificacaoService.TIMEOUT_SEGUNDOS)
        return argumentos.kwargs['json']

    def test_payload_com_remetente_destinatario_html_e_texto(self, post):
        NotificacaoService().enviar_confirmacao_cadastro(self.usuario)
        corpo = self.payload(post)
        self.assertEqual(corpo['sender'], {'email': 'contato@flori.test', 'name': 'Flori'})
        self.assertEqual(corpo['to'], [{'email': 'bia@exemplo.com', 'name': 'Bia'}])
        self.assertIn('https://flori.test/login.html', corpo['htmlContent'])
        self.assertIn('Bia', corpo['textContent'])

    def test_cada_email_usa_o_template_e_os_dados_certos(self, post):
        servico = NotificacaoService()
        casos = [
            (lambda: servico.enviar_recuperacao_senha(self.usuario, 'https://flori.test/r?t=abc', 30), 'https://flori.test/r?t=abc', 'bia@exemplo.com'),
            (lambda: servico.enviar_codigo_autenticacao(self.usuario, '123456', 15), '123456', 'bia@exemplo.com'),
            (lambda: servico.enviar_codigo_exclusao(self.usuario, '654321', 15), '654321', 'bia@exemplo.com'),
            (lambda: servico.enviar_codigo_troca_email('nova@exemplo.com', 'Bia', '111222', 15), '111222', 'nova@exemplo.com'),
            (lambda: servico.enviar_aviso_email_alterado('bia@exemplo.com', 'Bia', 'no****@exemplo.com'), 'no****@exemplo.com', 'bia@exemplo.com'),
            (lambda: servico.enviar_conta_excluida('bia@exemplo.com', 'Bia', pelo_admin=True), 'pela administração', 'bia@exemplo.com'),
            (lambda: servico.enviar_conta_excluida('bia@exemplo.com', 'Bia'), 'a seu pedido', 'bia@exemplo.com'),
        ]
        for enviar, esperado, destino in casos:
            post.reset_mock()
            enviar()
            corpo = self.payload(post)
            self.assertEqual(corpo['to'][0]['email'], destino)
            self.assertIn(esperado, corpo['textContent'])
            self.assertIn(esperado, corpo['htmlContent'])

    def test_falha_de_rede_vira_erro_de_notificacao(self, post):
        post.side_effect = requests.ConnectionError('sem rede')
        with self.assertRaises(ErroNotificacao):
            NotificacaoService().enviar_codigo_autenticacao(self.usuario, '123456')

    def test_resposta_de_erro_da_brevo_vira_erro_de_notificacao(self, post):
        resposta = MagicMock()
        resposta.raise_for_status.side_effect = requests.HTTPError('401 chave inválida')
        post.return_value = resposta
        with self.assertRaises(ErroNotificacao) as erro:
            NotificacaoService().enviar_conta_excluida('bia@exemplo.com', 'Bia')
        self.assertIn('Brevo', str(erro.exception))
