from datetime import date, timedelta
import logging
import math
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    CodigoAutenticacao, Consentimento, LogAtividade, SolicitacaoRedefinicaoSenha, Token, Usuario,
)
from .notificacoes import NotificacaoService

logger = logging.getLogger(__name__)

VERSAO_TERMOS_USO = '1.0'
VERSAO_POLITICA_PRIVACIDADE = '1.0'

TAMANHO_MAXIMO_NOME = 100
TAMANHO_MAXIMO_SOBRENOME = 100
TAMANHO_MAXIMO_APELIDO = 50
TAMANHO_MAXIMO_EMAIL = 150
TAMANHO_MAXIMO_CELULAR = 20


class ErroServico(Exception):
    STATUS_PADRAO = 400

    def __init__(self, mensagem, status=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status or self.STATUS_PADRAO


class ErroCadastro(ErroServico):
    pass


class ErroLogin(ErroServico):
    STATUS_PADRAO = 401


class ErroRedefinicaoSenha(ErroServico):
    def __init__(self, mensagem, status=None, espera_segundos=0):
        super().__init__(mensagem, status)
        self.espera_segundos = espera_segundos


def _texto(valor):
    return valor.strip() if isinstance(valor, str) else ''


def _senha(valor):
    return valor if isinstance(valor, str) else ''


def _capitalizar(texto):
    return ' '.join(palavra[:1].upper() + palavra[1:].lower() for palavra in texto.split())


class CadastroUsuario:
    VIA_GOOGLE = False

    def __init__(self, dados, ip_origem=None):
        self._dados = dados
        self.ip_origem = ip_origem
        self.nome = _capitalizar(_texto(dados.get('nome')))
        self.sobrenome = _capitalizar(_texto(dados.get('sobrenome')))
        self.apelido = _texto(dados.get('apelido'))
        self.email = _texto(dados.get('email')).lower() or None
        self.celular = _texto(dados.get('celular')) or None
        self.senha = _senha(dados.get('senha'))
        self.termos_aceitos = bool(dados.get('termos_aceitos'))
        self.data_nascimento = None

    def executar(self):
        self._validar_identificacao()
        self._validar_nascimento()
        self._validar_contato()
        self._validar_senha()
        self._validar_consentimento()
        return self._persistir()

    def _validar_identificacao(self):
        if not self.nome or not self.sobrenome:
            raise ErroCadastro('Nome e sobrenome são obrigatórios.')
        if len(self.nome) > TAMANHO_MAXIMO_NOME:
            raise ErroCadastro(f'Nome muito longo (máximo {TAMANHO_MAXIMO_NOME} caracteres).')
        if len(self.sobrenome) > TAMANHO_MAXIMO_SOBRENOME:
            raise ErroCadastro(f'Sobrenome muito longo (máximo {TAMANHO_MAXIMO_SOBRENOME} caracteres).')
        if len(self.apelido) > TAMANHO_MAXIMO_APELIDO:
            raise ErroCadastro(f'Apelido muito longo (máximo {TAMANHO_MAXIMO_APELIDO} caracteres).')

    def _validar_nascimento(self):
        bruto = self._dados.get('data_nascimento')
        if not bruto:
            raise ErroCadastro('Data de nascimento é obrigatória.')

        try:
            nascimento = date.fromisoformat(bruto)
        except (TypeError, ValueError):
            raise ErroCadastro('Data de nascimento inválida.')

        if nascimento > date.today():
            raise ErroCadastro('Data de nascimento não pode estar no futuro.')

        nascimento_formatado = nascimento.strftime('%d/%m/%Y')

        if not Usuario(data_nascimento=nascimento_formatado).tem_idade_minima():
            raise ErroCadastro('Ainda não é possível criar a conta com essa data de nascimento.')

        self.data_nascimento = nascimento_formatado

    def _validar_contato(self):
        if not self.email:
            raise ErroCadastro('E-mail é obrigatório.')
        if len(self.email) > TAMANHO_MAXIMO_EMAIL:
            raise ErroCadastro(f'E-mail muito longo (máximo {TAMANHO_MAXIMO_EMAIL} caracteres).')
        if self.celular and len(self.celular) > TAMANHO_MAXIMO_CELULAR:
            raise ErroCadastro(f'Celular muito longo (máximo {TAMANHO_MAXIMO_CELULAR} caracteres).')

    def _validar_senha(self):
        if len(self.senha) < Usuario.TAMANHO_MINIMO_SENHA:
            raise ErroCadastro(
                f'A senha precisa ter pelo menos {Usuario.TAMANHO_MINIMO_SENHA} caracteres.'
            )

    def _validar_consentimento(self):
        if not self.termos_aceitos:
            raise ErroCadastro('É necessário aceitar os termos de uso.')

    def _persistir(self):
        usuario = Usuario(
            nome=self.nome,
            sobrenome=self.sobrenome,
            apelido=self.apelido or self.nome[:TAMANHO_MAXIMO_APELIDO].strip(),
            data_nascimento=self.data_nascimento,
            email=self.email,
            celular=self.celular,
        )
        self._definir_senha(usuario)

        try:
            with transaction.atomic():
                usuario.save()
                self._registrar_consentimentos(usuario)
                LogAtividade.objects.create(
                    usuario=usuario,
                    acao=LogAtividade.Acao.CADASTRO,
                    ip_origem=self.ip_origem,
                )
        except IntegrityError:
            raise self._erro_de_duplicidade()

        self._enviar_boas_vindas(usuario)
        return usuario

    def _definir_senha(self, usuario):
        usuario.definir_senha(self.senha)

    def _registrar_consentimentos(self, usuario):
        Consentimento.objects.bulk_create([
            Consentimento(
                usuario=usuario,
                tipo=tipo,
                versao_documento=versao,
                aceito=True,
                ip_origem=self.ip_origem,
            )
            for tipo, versao in (
                (Consentimento.Tipo.TERMOS_USO, VERSAO_TERMOS_USO),
                (Consentimento.Tipo.POLITICA_PRIVACIDADE, VERSAO_POLITICA_PRIVACIDADE),
            )
        ])

    def _enviar_boas_vindas(self, usuario):
        try:
            NotificacaoService().enviar_confirmacao_cadastro(usuario, via_google=self.VIA_GOOGLE)
        except Exception:
            logger.exception('Falha ao enviar e-mail de confirmação de cadastro')

    def _erro_de_duplicidade(self):
        if self.email and Usuario.objects.filter(email=self.email).exists():
            return ErroCadastro('Esse e-mail já está em uso.', status=409)
        if self.celular and Usuario.objects.filter(celular=self.celular).exists():
            return ErroCadastro('Esse celular já está em uso.', status=409)
        return ErroCadastro('Não foi possível concluir o cadastro.', status=409)


def iniciar_sessao(usuario, ip_origem=None, acao=LogAtividade.Acao.LOGIN_SUCESSO):
    token = Token.objects.create(usuario=usuario)
    LogAtividade.objects.create(
        usuario=usuario,
        acao=acao,
        ip_origem=ip_origem,
    )
    return token


class ResultadoLogin:
    def __init__(self, usuario, token=None, desafio=None):
        self.usuario = usuario
        self.token = token
        self.desafio = desafio

    @property
    def requer_codigo(self):
        return self.desafio is not None


class LoginUsuario:
    def __init__(self, dados, ip_origem=None):
        self.ip_origem = ip_origem
        self.contato = (
            _texto(dados.get('contato')) or _texto(dados.get('email')) or _texto(dados.get('celular'))
        )
        self.senha = _senha(dados.get('senha'))

    def executar(self):
        if not self.contato or not self.senha:
            raise ErroLogin('Informe o contato e a senha.', status=400)

        usuario = (
            Usuario.objects.filter(email=self.contato.lower()).first()
            or Usuario.objects.filter(celular=self.contato).first()
        )

        if not usuario or not usuario.verificar_senha(self.senha):
            LogAtividade.objects.create(
                usuario=usuario,
                acao=LogAtividade.Acao.LOGIN_FALHA,
                ip_origem=self.ip_origem,
            )
            raise ErroLogin('Contato ou senha incorretos.', status=401)

        if not usuario.email:
            return ResultadoLogin(usuario, token=iniciar_sessao(usuario, self.ip_origem))

        desafio = EnviarCodigoAutenticacao(usuario, ip_origem=self.ip_origem).executar()
        return ResultadoLogin(usuario, desafio=desafio)


def mascarar_email(email):
    nome, _, dominio = email.partition('@')
    visivel = nome[:2] if len(nome) > 2 else nome[:1]
    return f'{visivel}{"*" * max(len(nome) - len(visivel), 1)}@{dominio}'


class EnviarCodigoAutenticacao:
    def __init__(self, usuario, ip_origem=None):
        self.usuario = usuario
        self.ip_origem = ip_origem

    def executar(self):
        agora = timezone.now()
        digitos = CodigoAutenticacao.QUANTIDADE_DIGITOS
        codigo = f'{secrets.randbelow(10 ** digitos):0{digitos}d}'
        desafio = secrets.token_urlsafe(32)

        with transaction.atomic():
            CodigoAutenticacao.objects.filter(
                usuario=self.usuario, usado_em__isnull=True, expira_em__gt=agora,
            ).update(expira_em=agora)

            registro = CodigoAutenticacao(
                usuario=self.usuario,
                desafio_hash=CodigoAutenticacao.gerar_hash_desafio(desafio),
                expira_em=agora + timedelta(minutes=CodigoAutenticacao.VALIDADE_MINUTOS),
                ip_origem=self.ip_origem,
            )
            registro.definir_codigo(codigo)
            registro.save()

        try:
            NotificacaoService().enviar_codigo_autenticacao(
                self.usuario, codigo, validade_minutos=CodigoAutenticacao.VALIDADE_MINUTOS,
            )
        except Exception:
            logger.exception('Falha ao enviar código de verificação (2FA)')
            registro.expira_em = agora
            registro.save(update_fields=['expira_em'])
            raise ErroLogin(
                'Não conseguimos enviar o código de verificação agora. Tente de novo em instantes.',
                status=503,
            )

        LogAtividade.objects.create(
            usuario=self.usuario,
            acao=LogAtividade.Acao.CODIGO_2FA_ENVIADO,
            ip_origem=self.ip_origem,
        )
        return desafio


class VerificarCodigoAutenticacao:
    MENSAGEM_CODIGO_INVALIDO = 'Código inválido. Tente novamente.'
    MENSAGEM_EXPIRADO = 'Este código expirou. Faça login de novo para receber um novo código.'

    def __init__(self, dados, ip_origem=None):
        self.ip_origem = ip_origem
        self.desafio = _texto(dados.get('desafio'))
        codigo = dados.get('codigo')
        self.codigo = ''.join(c for c in codigo if c.isdigit()) if isinstance(codigo, str) else ''

    def executar(self):
        if not self.desafio:
            raise ErroLogin(self.MENSAGEM_EXPIRADO, status=410)
        if len(self.codigo) != CodigoAutenticacao.QUANTIDADE_DIGITOS:
            raise ErroLogin(f'Digite os {CodigoAutenticacao.QUANTIDADE_DIGITOS} números do código.', status=400)

        agora = timezone.now()
        with transaction.atomic():
            registro = (
                CodigoAutenticacao.objects
                .select_for_update()
                .select_related('usuario')
                .filter(desafio_hash=CodigoAutenticacao.gerar_hash_desafio(self.desafio))
                .first()
            )
            erro = self._conferir(registro, agora)
            if not erro:
                registro.usado_em = agora
                registro.save(update_fields=['usado_em'])
                token = iniciar_sessao(registro.usuario, self.ip_origem)

        if erro:
            raise erro
        return registro.usuario, token

    def _conferir(self, registro, agora):
        if not registro or not registro.pode_ser_usado(agora):
            return ErroLogin(self.MENSAGEM_EXPIRADO, status=410)
        if registro.confere(self.codigo):
            return None

        registro.tentativas += 1
        registro.save(update_fields=['tentativas'])
        LogAtividade.objects.create(
            usuario=registro.usuario,
            acao=LogAtividade.Acao.CODIGO_2FA_INVALIDO,
            ip_origem=self.ip_origem,
        )
        if registro.tentativas >= CodigoAutenticacao.MAXIMO_TENTATIVAS:
            return ErroLogin(
                'Você errou o código muitas vezes. Faça login de novo para receber um novo código.',
                status=410,
            )
        return ErroLogin(self.MENSAGEM_CODIGO_INVALIDO, status=400)


def verificar_token_google(valor):
    from google.auth import exceptions as google_exceptions
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    id_token_google = _texto(valor)
    if not id_token_google:
        raise ErroLogin('Login com Google inválido. Tente de novo.', status=400)

    try:
        dados = id_token.verify_firebase_token(
            id_token_google, google_requests.Request(), audience=settings.FIREBASE_PROJECT_ID,
            clock_skew_in_seconds=60,
        )
    except ValueError as e:
        logger.warning('Token do Google recusado: %s', e)
        raise ErroLogin('Seu login com Google expirou ou é inválido. Tente de novo.', status=401)
    except google_exceptions.GoogleAuthError:
        logger.exception('Falha ao buscar as chaves públicas do Google')
        raise ErroLogin('Não conseguimos falar com o Google agora. Tente de novo em instantes.', status=503)

    provedor = dados.get('firebase', {}).get('sign_in_provider')
    email = (dados.get('email') or '').strip().lower()
    if provedor != 'google.com' or not email or not dados.get('email_verified'):
        raise ErroLogin('Não foi possível confirmar seu e-mail com o Google.', status=401)

    nome, _, sobrenome = (dados.get('name') or '').strip().partition(' ')
    return {
        'email': email, 'nome': nome, 'sobrenome': sobrenome.strip(),
        'foto': dados.get('picture') or None,
    }


class LoginGoogle:
    def __init__(self, dados, ip_origem=None):
        self.ip_origem = ip_origem
        self.id_token = dados.get('id_token')

    def executar(self):
        perfil = verificar_token_google(self.id_token)

        usuario = Usuario.objects.filter(email=perfil['email']).first()
        if not usuario:
            return None, None, perfil

        if perfil['foto'] and usuario.foto_url != perfil['foto']:
            usuario.foto_url = perfil['foto']
            usuario.save(update_fields=['foto_url'])

        token = iniciar_sessao(usuario, self.ip_origem, acao=LogAtividade.Acao.LOGIN_GOOGLE)
        return usuario, token, None


class CadastroUsuarioGoogle(CadastroUsuario):
    VIA_GOOGLE = True

    def __init__(self, dados, ip_origem=None):
        try:
            perfil = verificar_token_google(dados.get('id_token'))
        except ErroLogin as e:
            raise ErroCadastro(e.mensagem, status=e.status)

        dados = {**dados, 'email': perfil['email'], 'celular': None, 'senha': None}
        super().__init__(dados, ip_origem=ip_origem)
        self.foto_url = perfil['foto']

    def executar(self):
        usuario = super().executar()
        if self.foto_url:
            usuario.foto_url = self.foto_url
            usuario.save(update_fields=['foto_url'])
        return usuario

    def _validar_senha(self):
        pass

    def _definir_senha(self, usuario):
        usuario.definir_sem_senha()


class SolicitarRedefinicaoSenha:
    ESPERA_BASE_MINUTOS = 2
    ESPERA_MAXIMA_MINUTOS = 24 * 60
    JANELA_CONTAGEM = timedelta(hours=24)
    VALIDADE_TOKEN = timedelta(minutes=30)

    def __init__(self, dados, ip_origem=None):
        self.ip_origem = ip_origem
        self.email = _texto(dados.get('email')).lower()

    @classmethod
    def espera_apos(cls, quantidade_pedidos):
        minutos = cls.ESPERA_BASE_MINUTOS * 2 ** (quantidade_pedidos - 1)
        return timedelta(minutes=min(minutos, cls.ESPERA_MAXIMA_MINUTOS))

    def executar(self):
        self._validar_email()
        agora = timezone.now()
        quantidade = self._exigir_intervalo(agora)

        usuario = Usuario.objects.filter(email=self.email).first()
        token = secrets.token_urlsafe(32) if usuario else None
        self._registrar_pedido(usuario, token, agora)

        if usuario:
            self._enviar_link(usuario, token)

        return int(self.espera_apos(quantidade + 1).total_seconds())

    def _validar_email(self):
        if len(self.email) > TAMANHO_MAXIMO_EMAIL:
            raise ErroRedefinicaoSenha('Informe um e-mail válido.')
        try:
            validate_email(self.email)
        except ValidationError:
            raise ErroRedefinicaoSenha('Informe um e-mail válido.')

    def _exigir_intervalo(self, agora):
        anteriores = SolicitacaoRedefinicaoSenha.objects.filter(
            email=self.email, criado_em__gte=agora - self.JANELA_CONTAGEM,
        )
        quantidade = anteriores.count()
        if quantidade:
            ultimo = anteriores.latest('criado_em').criado_em
            liberado_em = ultimo + self.espera_apos(quantidade)
            if agora < liberado_em:
                espera = math.ceil((liberado_em - agora).total_seconds())
                raise ErroRedefinicaoSenha(
                    'Aguarde um pouco antes de pedir um novo e-mail.',
                    status=429, espera_segundos=espera,
                )
        return quantidade

    def _registrar_pedido(self, usuario, token, agora):
        with transaction.atomic():
            SolicitacaoRedefinicaoSenha.objects.create(
                email=self.email,
                usuario=usuario,
                token_hash=SolicitacaoRedefinicaoSenha.gerar_hash(token) if token else None,
                expira_em=agora + self.VALIDADE_TOKEN if token else None,
                ip_origem=self.ip_origem,
            )
            if usuario:
                LogAtividade.objects.create(
                    usuario=usuario,
                    acao=LogAtividade.Acao.REDEFINICAO_SENHA_SOLICITADA,
                    ip_origem=self.ip_origem,
                )

    def _enviar_link(self, usuario, token):
        link = f'{settings.FRONTEND_URL}/redefinir-senha.html?token={token}'
        try:
            NotificacaoService().enviar_recuperacao_senha(
                usuario, link, validade_minutos=int(self.VALIDADE_TOKEN.total_seconds() // 60),
            )
        except Exception:
            logger.exception('Falha ao enviar e-mail de redefinição de senha')


class ConfirmarRedefinicaoSenha:
    MENSAGEM_LINK_INVALIDO = 'Este link é inválido ou expirou. Peça um novo em "Esqueci minha senha".'

    def __init__(self, dados, ip_origem=None):
        self.ip_origem = ip_origem
        self.token = _texto(dados.get('token'))
        self.senha = _senha(dados.get('senha'))

    def executar(self):
        if not self.token:
            raise ErroRedefinicaoSenha(self.MENSAGEM_LINK_INVALIDO)
        if len(self.senha) < Usuario.TAMANHO_MINIMO_SENHA:
            raise ErroRedefinicaoSenha(
                f'A senha precisa ter pelo menos {Usuario.TAMANHO_MINIMO_SENHA} caracteres.'
            )

        agora = timezone.now()
        with transaction.atomic():
            pedido = (
                SolicitacaoRedefinicaoSenha.objects
                .select_for_update()
                .select_related('usuario')
                .filter(
                    token_hash=SolicitacaoRedefinicaoSenha.gerar_hash(self.token),
                    usado_em__isnull=True,
                    expira_em__gt=agora,
                )
                .first()
            )
            if not pedido or not pedido.usuario:
                raise ErroRedefinicaoSenha(self.MENSAGEM_LINK_INVALIDO)

            usuario = pedido.usuario
            usuario.definir_senha(self.senha)
            usuario.save(update_fields=['senha_hash'])

            SolicitacaoRedefinicaoSenha.objects.filter(
                usuario=usuario, usado_em__isnull=True,
            ).update(usado_em=agora)
            Token.objects.filter(usuario=usuario).delete()
            LogAtividade.objects.create(
                usuario=usuario,
                acao=LogAtividade.Acao.SENHA_REDEFINIDA,
                ip_origem=self.ip_origem,
            )

        return usuario


class ErroPerfil(Exception):
    def __init__(self, mensagem, status=400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


class AtualizarPerfil:
    def __init__(self, usuario, dados):
        self.usuario = usuario
        self._dados = dados

    def executar(self):
        usuario = self.usuario
        if 'nome' in self._dados:
            usuario.nome = self._nome('nome', 'Nome', TAMANHO_MAXIMO_NOME)
        if 'sobrenome' in self._dados:
            usuario.sobrenome = self._nome('sobrenome', 'Sobrenome', TAMANHO_MAXIMO_SOBRENOME)
        if 'apelido' in self._dados:
            apelido = self._texto('apelido')
            if len(apelido) > TAMANHO_MAXIMO_APELIDO:
                raise ErroPerfil(f'Apelido muito longo (máximo {TAMANHO_MAXIMO_APELIDO} caracteres).')
            usuario.apelido = apelido or usuario.nome
        if 'celular' in self._dados:
            usuario.celular = self._celular()

        try:
            usuario.save()
        except IntegrityError:
            raise ErroPerfil('Esse celular já está em uso.', status=409)
        return usuario

    def _texto(self, campo):
        valor = self._dados.get(campo)
        return valor.strip() if isinstance(valor, str) else ''

    def _nome(self, campo, rotulo, maximo):
        texto = ' '.join(p[:1].upper() + p[1:].lower() for p in self._texto(campo).split())
        if not texto:
            raise ErroPerfil(f'{rotulo} é obrigatório.')
        if len(texto) > maximo:
            raise ErroPerfil(f'{rotulo} muito longo (máximo {maximo} caracteres).')
        return texto

    def _celular(self):
        celular = self._texto('celular')
        if not celular:
            return None
        digitos = sum(c.isdigit() for c in celular)
        if not 10 <= digitos <= 13:
            raise ErroPerfil('Celular inválido. Informe o DDD e o número.')
        return celular


class AlterarConsentimento:
    def __init__(self, usuario, dados, ip_origem=None):
        self.usuario = usuario
        self.tipo = dados.get('tipo')
        self.aceito = dados.get('aceito')
        self.ip_origem = ip_origem

    def executar(self):
        atuais = self.usuario.consentimentos_atuais()
        if self.tipo not in atuais or not isinstance(self.aceito, bool):
            raise ErroPerfil('Consentimento inválido.')
        atual = atuais[self.tipo]
        if atual.aceito == self.aceito:
            return atual
        return Consentimento.objects.create(
            usuario=self.usuario, tipo=self.tipo, versao_documento=atual.versao_documento,
            aceito=self.aceito, ip_origem=self.ip_origem,
        )
