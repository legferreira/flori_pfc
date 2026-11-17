import requests
from django.conf import settings
from django.template.loader import render_to_string


class ErroNotificacao(Exception):
    pass


class NotificacaoService:
    URL_ENVIO = 'https://api.brevo.com/v3/smtp/email'
    NOME_REMETENTE = 'Flori'
    TIMEOUT_SEGUNDOS = 5

    def __init__(self):
        self.api_key = settings.BREVO_API_KEY
        self.email_remetente = settings.BREVO_REMETENTE_EMAIL

    def _enviar(self, destinatario_email, destinatario_nome, assunto, conteudo_html, conteudo_texto=None):
        payload = {
            'sender': {'email': self.email_remetente, 'name': self.NOME_REMETENTE},
            'to': [{'email': destinatario_email, 'name': destinatario_nome}],
            'subject': assunto,
            'htmlContent': conteudo_html,
        }
        if conteudo_texto:
            payload['textContent'] = conteudo_texto
        headers = {
            'api-key': self.api_key,
            'Content-Type': 'application/json',
        }
        try:
            resposta = requests.post(self.URL_ENVIO, json=payload, headers=headers, timeout=self.TIMEOUT_SEGUNDOS)
            resposta.raise_for_status()
        except requests.RequestException as e:
            raise ErroNotificacao(f'Falha ao enviar e-mail via Brevo: {e}')

    def _enviar_template(self, usuario, assunto, template, **contexto):
        contexto = {'apelido': usuario.apelido, **contexto}
        self._enviar(
            usuario.email, usuario.apelido, assunto,
            render_to_string(f'users/emails/{template}.html', contexto),
            conteudo_texto=render_to_string(f'users/emails/{template}.txt', contexto),
        )

    def enviar_confirmacao_cadastro(self, usuario, via_google=False):
        self._enviar_template(
            usuario, 'Bem-vinda ao Flori!', 'boas_vindas',
            link=f'{settings.FRONTEND_URL}/login.html', via_google=via_google,
        )

    def enviar_recuperacao_senha(self, usuario, link_redefinicao, validade_minutos=30):
        self._enviar_template(
            usuario, 'Redefinição de senha, Flori', 'redefinir_senha',
            link=link_redefinicao, validade_minutos=validade_minutos,
        )

    def enviar_codigo_autenticacao(self, usuario, codigo, validade_minutos=15):
        self._enviar_template(
            usuario, 'Seu código de acesso, Flori', 'codigo_autenticacao',
            codigo=codigo, validade_minutos=validade_minutos,
        )

    def enviar_codigo_exclusao(self, usuario, codigo, validade_minutos=15):
        self._enviar_template(
            usuario, 'Código para excluir sua conta no Flori', 'codigo_exclusao',
            codigo=codigo, validade_minutos=validade_minutos,
        )

    def _enviar_para(self, email, apelido, assunto, template, **contexto):
        contexto = {'apelido': apelido, **contexto}
        self._enviar(
            email, apelido, assunto,
            render_to_string(f'users/emails/{template}.html', contexto),
            conteudo_texto=render_to_string(f'users/emails/{template}.txt', contexto),
        )

    def enviar_conta_excluida(self, email, apelido, pelo_admin=False):
        self._enviar_para(email, apelido, 'Sua conta no Flori foi excluída', 'conta_excluida', pelo_admin=pelo_admin)

    def enviar_codigo_troca_email(self, email_novo, apelido, codigo, validade_minutos=15):
        self._enviar_para(
            email_novo, apelido, 'Confirme seu novo email no Flori', 'codigo_troca_email',
            codigo=codigo, validade_minutos=validade_minutos,
        )

    def enviar_aviso_email_alterado(self, email_antigo, apelido, email_novo_mascarado):
        self._enviar_para(
            email_antigo, apelido, 'O email da sua conta no Flori foi alterado', 'email_alterado',
            email_novo_mascarado=email_novo_mascarado,
        )
