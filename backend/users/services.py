from datetime import date, timedelta
import logging
import math
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from flori_backend.api import momento_exibicao, momento_iso
from diario.services import apagar_diario, registros_com_sintomas
from trilha.models import Certificado, ProgressoCard, ProgressoTrilha, TentativaQuiz

from .auditoria import registrar_log, registrar_log_admin
from .models import (
    CodigoAutenticacao, Consentimento, LogAtividade, SolicitacaoRedefinicaoSenha,
    TentativaLogin, Token, TrocaEmailPendente, Usuario,
)
from .notificacoes import NotificacaoService

logger = logging.getLogger(__name__)

VERSAO_TERMOS_USO = '2.0'
VERSAO_POLITICA_PRIVACIDADE = '2.0'
VERSAO_CONSENTIMENTO_SAUDE = '1.0'
VERSOES_VIGENTES = {
    Consentimento.Tipo.TERMOS_USO: VERSAO_TERMOS_USO,
    Consentimento.Tipo.POLITICA_PRIVACIDADE: VERSAO_POLITICA_PRIVACIDADE,
}
VERSOES_CONSENTIMENTOS = {**VERSOES_VIGENTES, Consentimento.Tipo.SAUDE: VERSAO_CONSENTIMENTO_SAUDE}


def documentos_desatualizados(usuario):
    return [
        tipo for tipo, c in usuario.consentimentos_atuais().items()
        if c.aceito and tipo in VERSOES_VIGENTES and c.versao_documento != VERSOES_VIGENTES[tipo]
    ]


class AceitarDocumentosAtualizados:
    def __init__(self, usuario, ip_origem=None):
        self.usuario = usuario
        self.ip_origem = ip_origem

    def executar(self):
        with transaction.atomic():
            Usuario.objects.select_for_update().filter(pk=self.usuario.pk).first()
            pendentes = documentos_desatualizados(self.usuario)
            if not pendentes:
                return {}
            versoes = {tipo: VERSOES_VIGENTES[tipo] for tipo in pendentes}
            Consentimento.objects.bulk_create([
                Consentimento(
                    usuario=self.usuario, tipo=tipo, versao_documento=versao, aceito=True, ip_origem=self.ip_origem,
                )
                for tipo, versao in versoes.items()
            ])
            registrar_log(
                self.usuario, LogAtividade.Acao.DOCUMENTOS_ACEITOS, self.ip_origem,
                alvo_tipo='consentimento', alvo_id=self.usuario.id, resumo={'versoes': versoes},
            )
        return versoes


TAMANHO_MAXIMO_NOME = 100
TAMANHO_MAXIMO_SOBRENOME = 100
TAMANHO_MAXIMO_APELIDO = 50
TAMANHO_MAXIMO_EMAIL = 150
TAMANHO_MAXIMO_CELULAR = 20


class ErroServico(Exception):
    STATUS_PADRAO = 400

    def __init__(self, mensagem, status=None, campos=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status or self.STATUS_PADRAO
        self.campos = campos


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


def gerar_codigo_numerico():
    digitos = CodigoAutenticacao.QUANTIDADE_DIGITOS
    return f'{secrets.randbelow(10 ** digitos):0{digitos}d}'


def _apenas_digitos(valor):
    return ''.join(c for c in valor if c.isdigit()) if isinstance(valor, str) else ''


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
    if usuario.is_admin:
        registrar_log_admin(
            usuario, LogAtividade.Acao.ADMIN_LOGIN, 'usuario', usuario.id,
            {'metodo': 'google' if acao == LogAtividade.Acao.LOGIN_GOOGLE else 'senha'}, ip_origem,
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
    JANELA_BLOQUEIO = timedelta(minutes=15)
    MAXIMO_FALHAS_POR_CONTATO = 5
    MAXIMO_FALHAS_POR_IP = 20

    def __init__(self, dados, ip_origem=None):
        self.ip_origem = ip_origem
        self.contato = (
            _texto(dados.get('contato')) or _texto(dados.get('email')) or _texto(dados.get('celular'))
        )
        self.senha = _senha(dados.get('senha'))

    def executar(self):
        if not self.contato or not self.senha:
            raise ErroLogin('Informe o contato e a senha.', status=400)

        contato_hash = TentativaLogin.gerar_hash(self.contato)
        self._exigir_sem_bloqueio(contato_hash)

        usuario = (
            Usuario.objects.ativos().filter(email=self.contato.lower()).first()
            or Usuario.objects.ativos().filter(celular=self.contato).first()
        )

        if not usuario or not usuario.verificar_senha(self.senha):
            TentativaLogin.objects.create(contato_hash=contato_hash, ip_origem=self.ip_origem)
            LogAtividade.objects.create(
                usuario=usuario,
                acao=LogAtividade.Acao.LOGIN_FALHA,
                ip_origem=self.ip_origem,
            )
            raise ErroLogin('Contato ou senha incorretos.', status=401)

        TentativaLogin.objects.filter(contato_hash=contato_hash).delete()

        if not usuario.email:
            if usuario.is_admin:
                raise ErroLogin('Conta admin precisa de email para receber o código de verificação.', status=403)
            return ResultadoLogin(usuario, token=iniciar_sessao(usuario, self.ip_origem))

        desafio = EnviarCodigoAutenticacao(usuario, ip_origem=self.ip_origem).executar()
        return ResultadoLogin(usuario, desafio=desafio)

    def _exigir_sem_bloqueio(self, contato_hash):
        desde = timezone.now() - self.JANELA_BLOQUEIO
        recentes = TentativaLogin.objects.filter(criado_em__gte=desde)
        bloqueado = recentes.filter(contato_hash=contato_hash).count() >= self.MAXIMO_FALHAS_POR_CONTATO
        if not bloqueado and self.ip_origem:
            bloqueado = recentes.filter(ip_origem=self.ip_origem).count() >= self.MAXIMO_FALHAS_POR_IP
        if bloqueado:
            LogAtividade.objects.create(acao=LogAtividade.Acao.LOGIN_BLOQUEADO, ip_origem=self.ip_origem)
            minutos = int(self.JANELA_BLOQUEIO.total_seconds() // 60)
            raise ErroLogin(
                f'Muitas tentativas de login. Aguarde {minutos} minutos e tente de novo.', status=429,
            )


def mascarar_email(email):
    nome, _, dominio = email.partition('@')
    return f'{nome[:min(2, max(len(nome) - 1, 0))]}****@{dominio}'


class EnviarCodigoAutenticacao:
    def __init__(self, usuario, ip_origem=None, finalidade='login'):
        self.usuario = usuario
        self.ip_origem = ip_origem
        self.finalidade = finalidade

    def executar(self):
        agora = timezone.now()
        codigo = gerar_codigo_numerico()
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

        notificacao = NotificacaoService()
        enviar = (
            notificacao.enviar_codigo_exclusao if self.finalidade == 'exclusao'
            else notificacao.enviar_codigo_autenticacao
        )
        try:
            enviar(self.usuario, codigo, validade_minutos=CodigoAutenticacao.VALIDADE_MINUTOS)
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
        if not registro or not registro.usuario.ativo or not registro.pode_ser_usado(agora):
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

        usuario = Usuario.objects.ativos().filter(email=perfil['email']).first()
        if not usuario:
            return None, perfil

        if perfil['foto'] and usuario.foto_url != perfil['foto']:
            usuario.foto_url = perfil['foto']
            usuario.save(update_fields=['foto_url'])

        if usuario.is_admin:
            desafio = EnviarCodigoAutenticacao(usuario, ip_origem=self.ip_origem).executar()
            return ResultadoLogin(usuario, desafio=desafio), None

        token = iniciar_sessao(usuario, self.ip_origem, acao=LogAtividade.Acao.LOGIN_GOOGLE)
        return ResultadoLogin(usuario, token=token), None


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

        usuario = Usuario.objects.ativos().filter(email=self.email).first()
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
            if not pedido or not pedido.usuario or not pedido.usuario.ativo:
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
    CAMPOS = ('nome', 'sobrenome', 'apelido', 'celular')

    def __init__(self, usuario, dados, ip_origem=None):
        self.usuario = usuario
        self._dados = dados
        self.ip_origem = ip_origem

    def executar(self):
        usuario = self.usuario
        antes = {campo: getattr(usuario, campo) for campo in self.CAMPOS}
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

        depois = {campo: getattr(usuario, campo) for campo in self.CAMPOS}
        alterados = sorted(c for c in self.CAMPOS if antes[c] != depois[c])
        if not alterados:
            return usuario

        try:
            with transaction.atomic():
                usuario.save()
                registrar_log(
                    usuario, LogAtividade.Acao.PERFIL_ATUALIZADO, self.ip_origem,
                    alvo_tipo='usuario', alvo_id=usuario.id,
                    resumo={'campos': alterados},
                )
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
        primeiro_aceite_saude = self.tipo == Consentimento.Tipo.SAUDE and self.tipo not in atuais
        if not isinstance(self.aceito, bool) or (self.tipo not in atuais and not primeiro_aceite_saude):
            raise ErroPerfil('Consentimento inválido.')
        if self.tipo == Consentimento.Tipo.SAUDE and self.usuario.is_admin:
            raise ErroPerfil('O perfil admin não usa o diário do corpo.', status=403)
        atual = atuais.get(self.tipo)
        if primeiro_aceite_saude and not self.aceito:
            return None
        if atual and atual.aceito == self.aceito:
            return atual
        acao = LogAtividade.Acao.CONSENTIMENTO_REATIVADO if self.aceito else LogAtividade.Acao.CONSENTIMENTO_REVOGADO
        versao = VERSOES_CONSENTIMENTOS[self.tipo] if self.aceito else atual.versao_documento
        with transaction.atomic():
            novo = Consentimento.objects.create(
                usuario=self.usuario, tipo=self.tipo, versao_documento=versao,
                aceito=self.aceito, ip_origem=self.ip_origem,
            )
            registrar_log(
                self.usuario, acao, self.ip_origem, alvo_tipo='consentimento', alvo_id=novo.id,
                resumo={'tipo': self.tipo, 'versao_documento': novo.versao_documento},
            )
        return novo


class ErroExclusao(ErroServico):
    pass


class ExcluirConta:
    def __init__(
        self, usuario_id, ip_origem=None, ator=None, motivo='', acao=LogAtividade.Acao.EXCLUSAO_CONTA_PROPRIA,
    ):
        self.usuario_id = usuario_id
        self.ip_origem = ip_origem
        self.ator = ator
        self.motivo = motivo
        self.acao = acao

    def executar(self):
        with transaction.atomic():
            usuario = Usuario.objects.select_for_update().filter(pk=self.usuario_id).first()
            if usuario is None or not usuario.ativo:
                return None
            if usuario.is_admin:
                raise ErroExclusao('Conta admin não pode ser excluída.', status=403)

            contato = {'id': usuario.id, 'email': usuario.email, 'apelido': usuario.apelido}
            self._apagar_vinculos(usuario)
            usuario.anonimizar(timezone.now())
            usuario.save()
            self._registrar(usuario)
        return contato

    def _apagar_vinculos(self, usuario):
        Token.objects.filter(usuario=usuario).delete()
        CodigoAutenticacao.objects.filter(usuario=usuario).delete()
        TrocaEmailPendente.objects.filter(usuario=usuario).delete()
        solicitacoes = Q(usuario=usuario)
        if usuario.email:
            solicitacoes |= Q(email=usuario.email)
        SolicitacaoRedefinicaoSenha.objects.filter(solicitacoes).delete()
        contatos = [TentativaLogin.gerar_hash(c) for c in (usuario.email, usuario.celular) if c]
        TentativaLogin.objects.filter(contato_hash__in=contatos).delete()
        Certificado.objects.filter(usuario=usuario).delete()
        TentativaQuiz.objects.filter(usuario=usuario).delete()
        ProgressoCard.objects.filter(usuario=usuario).delete()
        ProgressoTrilha.objects.filter(usuario=usuario).delete()
        apagar_diario(usuario)

    def _registrar(self, usuario):
        if self.ator is not None:
            registrar_log_admin(
                self.ator, LogAtividade.Acao.ADMIN_USER_EXCLUIDO, 'usuario', usuario.id,
                {'motivo': self.motivo}, self.ip_origem,
            )
        else:
            registrar_log(usuario, self.acao, self.ip_origem, alvo_tipo='usuario', alvo_id=usuario.id)


class ExcluirContaPropria:
    TEXTO_CONFIRMACAO = 'EXCLUIR'
    JANELA_RECUSAS = timedelta(minutes=15)
    MAXIMO_RECUSAS = 5

    def __init__(self, usuario, dados, ip_origem=None):
        self.usuario = usuario
        self.ip_origem = ip_origem
        self.confirmacao = _texto(dados.get('confirmacao'))
        self.senha = _senha(dados.get('senha'))
        self.desafio = _texto(dados.get('desafio'))
        codigo = dados.get('codigo')
        self.codigo = ''.join(c for c in codigo if c.isdigit()) if isinstance(codigo, str) else ''

    def executar(self):
        if self.usuario.is_admin:
            raise ErroExclusao('Conta admin não pode ser excluída.', status=403)
        self._exigir_sem_bloqueio()
        if self.confirmacao != self.TEXTO_CONFIRMACAO:
            raise ErroExclusao(f'Digite {self.TEXTO_CONFIRMACAO} para confirmar a exclusão.')
        if self.usuario.tem_senha():
            if not self.senha or not self.usuario.verificar_senha(self.senha):
                self._recusar('Senha incorreta. Sua conta não foi excluída.')
        else:
            self._conferir_codigo()

        contato = ExcluirConta(self.usuario.id, ip_origem=self.ip_origem).executar()
        if contato and contato['email']:
            try:
                NotificacaoService().enviar_conta_excluida(contato['email'], contato['apelido'])
            except Exception:
                logger.exception('Falha ao enviar email de confirmação de exclusão de conta')
        return contato

    def _exigir_sem_bloqueio(self):
        recusas = LogAtividade.objects.filter(
            usuario=self.usuario, acao=LogAtividade.Acao.EXCLUSAO_CONTA_RECUSADA,
            criado_em__gte=timezone.now() - self.JANELA_RECUSAS,
        ).count()
        if recusas >= self.MAXIMO_RECUSAS:
            raise ErroExclusao('Muitas tentativas. Aguarde alguns minutos e tente de novo.', status=429)

    def _recusar(self, mensagem):
        registrar_log(self.usuario, LogAtividade.Acao.EXCLUSAO_CONTA_RECUSADA, self.ip_origem)
        raise ErroExclusao(mensagem, status=403)

    def _conferir_codigo(self):
        if not self.desafio or len(self.codigo) != CodigoAutenticacao.QUANTIDADE_DIGITOS:
            raise ErroExclusao('Informe o código que enviamos para o seu email.')
        agora = timezone.now()
        registro = CodigoAutenticacao.objects.filter(
            usuario=self.usuario, desafio_hash=CodigoAutenticacao.gerar_hash_desafio(self.desafio),
        ).first()
        if not registro or not registro.pode_ser_usado(agora):
            self._recusar('Este código expirou. Peça um novo código.')
        if not registro.confere(self.codigo):
            registro.tentativas += 1
            registro.save(update_fields=['tentativas'])
            self._recusar('Código inválido. Sua conta não foi excluída.')
        registro.usado_em = agora
        registro.save(update_fields=['usado_em'])


class EnviarCodigoExclusao:
    JANELA = timedelta(minutes=15)
    MAXIMO_CODIGOS = 3

    def __init__(self, usuario, ip_origem=None):
        self.usuario = usuario
        self.ip_origem = ip_origem

    def executar(self):
        if self.usuario.is_admin:
            raise ErroExclusao('Conta admin não pode ser excluída.', status=403)
        if self.usuario.tem_senha():
            raise ErroExclusao('Sua conta tem senha. Use a senha para confirmar a exclusão.')
        if not self.usuario.email:
            raise ErroExclusao('Sua conta não tem email para receber o código.')
        recentes = CodigoAutenticacao.objects.filter(
            usuario=self.usuario, criado_em__gte=timezone.now() - self.JANELA,
        ).count()
        if recentes >= self.MAXIMO_CODIGOS:
            raise ErroExclusao('Você já pediu vários códigos. Aguarde alguns minutos.', status=429)
        return EnviarCodigoAutenticacao(self.usuario, ip_origem=self.ip_origem, finalidade='exclusao').executar()


class ExportarDados:
    LIMITE_POR_HORA = 5

    def __init__(self, usuario, ip_origem=None):
        self.usuario = usuario
        self.ip_origem = ip_origem

    def executar(self):
        recentes = LogAtividade.objects.filter(
            usuario=self.usuario, acao=LogAtividade.Acao.EXPORTACAO_DADOS,
            criado_em__gte=timezone.now() - timedelta(hours=1),
        ).count()
        if recentes >= self.LIMITE_POR_HORA:
            raise ErroServico(
                f'Você pode baixar seus dados até {self.LIMITE_POR_HORA} vezes por hora. Tente de novo mais tarde.',
                status=429,
            )
        dados = self._montar()
        registrar_log(self.usuario, LogAtividade.Acao.EXPORTACAO_DADOS, self.ip_origem)
        return dados

    def _montar(self):
        u = self.usuario
        historico = u.consentimentos.order_by('data_consentimento')
        return {
            'gerado_em': momento_iso(timezone.now()),
            'perfil': {
                'id': str(u.id), 'nome': u.nome, 'sobrenome': u.sobrenome, 'apelido': u.apelido,
                'email': u.email, 'celular': u.celular, 'data_nascimento': u.data_nascimento,
                'foto_url': u.foto_url, 'perfil': u.perfil, 'conta_com_senha': u.tem_senha(),
                'criado_em': momento_iso(u.criado_em),
            },
            'consentimentos': {
                'atuais': [
                    {'tipo': c.tipo, 'versao_documento': c.versao_documento, 'aceito': c.aceito,
                     'data': momento_iso(c.data_consentimento)}
                    for c in u.consentimentos_atuais().values()
                ],
                'historico': [
                    {'tipo': c.tipo, 'versao_documento': c.versao_documento, 'aceito': c.aceito,
                     'data': momento_iso(c.data_consentimento), 'ip_origem': c.ip_origem}
                    for c in historico
                ],
            },
            'progresso_cards': [
                {'card': p.card.codigo, 'tema': p.card.tema, 'concluido_em': momento_iso(p.concluido_em)}
                for p in ProgressoCard.objects.filter(usuario=u).select_related('card').order_by('concluido_em')
            ],
            'tentativas_quiz': [
                {'acertos': t.acertos, 'total_perguntas': t.total_perguntas, 'percentual': t.percentual,
                 'aprovada': t.aprovada, 'data': momento_iso(t.criado_em), 'finalizada_em': momento_iso(t.finalizada_em)}
                for t in TentativaQuiz.objects.filter(usuario=u).order_by('criado_em')
            ],
            'situacao_menstrual': u.situacao_menstrual,
            'diario': [
                {
                    'data': r.data.isoformat(), 'fluxo': r.fluxo, 'humor': r.humor,
                    'sintomas': [{'sintoma': rs.sintoma.nome, 'intensidade': rs.intensidade} for rs in r.sintomas.all()],
                }
                for r in registros_com_sintomas(u).order_by('data')
            ],
            'certificados': [
                {'codigo': c.codigo, 'nome_completo': c.nome_completo, 'trilha': c.trilha.nome,
                 'emitido_em': momento_iso(c.emitido_em)}
                for c in Certificado.objects.filter(usuario=u).select_related('trilha')
            ],
            'atividades': [
                {'acao': log.acao, 'descricao': log.get_acao_display(), 'data': momento_iso(log.criado_em),
                 'data_exibicao': momento_exibicao(log.criado_em)}
                for log in LogAtividade.objects.filter(usuario=u).order_by('-criado_em')
            ],
        }


class ErroTrocaEmail(ErroServico):
    pass


class SolicitarTrocaEmail:
    LIMITE_POR_HORA = 3
    MENSAGEM = 'Se o email informado puder ser usado, enviamos um código para ele. O código vale por {minutos} minutos.'

    def __init__(self, usuario, dados, ip_origem=None):
        self.usuario = usuario
        self.ip_origem = ip_origem
        self.email_novo = _texto(dados.get('email_novo')).lower()
        self.senha = _senha(dados.get('senha'))

    def executar(self):
        if not self.usuario.tem_senha():
            self._recusar('conta_google', 'Contas que entram com Google não podem trocar o email por aqui.', 403)
        self._validar_formato()
        if self._solicitacoes_recentes() >= self.LIMITE_POR_HORA:
            self._recusar('limite_excedido', 'Você já pediu a troca de email várias vezes. Tente de novo em uma hora.', 429)
        if not self.senha or not self.usuario.verificar_senha(self.senha):
            self._recusar('senha_incorreta', 'Senha incorreta.', 403)
        if self.email_novo == (self.usuario.email or '').lower():
            raise ErroTrocaEmail('Esse já é o email da sua conta.')

        if Usuario.objects.filter(email=self.email_novo).exclude(pk=self.usuario.pk).exists():
            TrocaEmailPendente.objects.filter(usuario=self.usuario).delete()
            self._registrar_recusa('email_em_uso')
            return self._resposta()

        codigo = gerar_codigo_numerico()
        with transaction.atomic():
            TrocaEmailPendente.objects.filter(usuario=self.usuario).delete()
            pendente = TrocaEmailPendente(
                usuario=self.usuario, email_novo=self.email_novo,
                expira_em=timezone.now() + timedelta(minutes=TrocaEmailPendente.VALIDADE_MINUTOS),
            )
            pendente.definir_codigo(codigo)
            pendente.save()
            registrar_log(
                self.usuario, LogAtividade.Acao.EMAIL_ALTERACAO_SOLICITADA, self.ip_origem,
                alvo_tipo='usuario', alvo_id=self.usuario.id, resumo={'destino': mascarar_email(self.email_novo)},
            )

        try:
            NotificacaoService().enviar_codigo_troca_email(
                self.email_novo, self.usuario.apelido, codigo, TrocaEmailPendente.VALIDADE_MINUTOS,
            )
        except Exception:
            logger.exception('Falha ao enviar código de troca de email')
            TrocaEmailPendente.objects.filter(pk=pendente.pk).delete()
            raise ErroTrocaEmail('Não conseguimos enviar o código agora. Tente de novo em instantes.', status=503)
        return self._resposta()

    def _validar_formato(self):
        if not self.email_novo or len(self.email_novo) > TAMANHO_MAXIMO_EMAIL:
            raise ErroTrocaEmail('Informe um email válido.')
        try:
            validate_email(self.email_novo)
        except ValidationError:
            raise ErroTrocaEmail('Informe um email válido.')

    def _solicitacoes_recentes(self):
        return LogAtividade.objects.filter(
            Q(acao=LogAtividade.Acao.EMAIL_ALTERACAO_SOLICITADA)
            | Q(acao=LogAtividade.Acao.EMAIL_ALTERACAO_RECUSADA, resumo__motivo__in=['email_em_uso', 'senha_incorreta']),
            usuario=self.usuario, criado_em__gte=timezone.now() - timedelta(hours=1),
        ).count()

    def _registrar_recusa(self, motivo):
        resumo = {'motivo': motivo}
        if motivo == 'email_em_uso':
            resumo['destino'] = mascarar_email(self.email_novo)
        registrar_log(
            self.usuario, LogAtividade.Acao.EMAIL_ALTERACAO_RECUSADA, self.ip_origem,
            alvo_tipo='usuario', alvo_id=self.usuario.id, resumo=resumo,
        )

    def _recusar(self, motivo, mensagem, status):
        self._registrar_recusa(motivo)
        raise ErroTrocaEmail(mensagem, status=status)

    def _resposta(self):
        return {
            'mensagem': self.MENSAGEM.format(minutos=TrocaEmailPendente.VALIDADE_MINUTOS),
            'email_mascarado': mascarar_email(self.email_novo),
            'validade_minutos': TrocaEmailPendente.VALIDADE_MINUTOS,
        }


class ConfirmarTrocaEmail:
    MENSAGEM_SEM_TROCA = 'Não há troca de email pendente. Peça um novo código.'

    def __init__(self, usuario, token_atual, dados, ip_origem=None):
        self.usuario = usuario
        self.token_atual = token_atual
        self.ip_origem = ip_origem
        self.codigo = _apenas_digitos(dados.get('codigo'))

    def executar(self):
        if len(self.codigo) != CodigoAutenticacao.QUANTIDADE_DIGITOS:
            raise ErroTrocaEmail(f'Digite os {CodigoAutenticacao.QUANTIDADE_DIGITOS} números do código.')

        pendente = TrocaEmailPendente.objects.filter(usuario=self.usuario).first()
        if pendente is None:
            raise ErroTrocaEmail(self.MENSAGEM_SEM_TROCA, status=410)
        if pendente.expirada(timezone.now()):
            pendente.delete()
            self._log(LogAtividade.Acao.EMAIL_ALTERACAO_EXPIRADA, pendente.email_novo)
            raise ErroTrocaEmail('Este código expirou. Peça um novo código.', status=410)
        if not pendente.confere(self.codigo):
            self._codigo_errado(pendente)

        email_antigo = self.usuario.email
        email_novo = pendente.email_novo
        try:
            with transaction.atomic():
                TrocaEmailPendente.objects.select_for_update().get(pk=pendente.pk)
                if Usuario.objects.filter(email=email_novo).exclude(pk=self.usuario.pk).exists():
                    raise IntegrityError
                self.usuario.email = email_novo
                self.usuario.save(update_fields=['email'])
                self._encerrar_pendencias(email_antigo)
                TrocaEmailPendente.objects.filter(pk=pendente.pk).delete()
                registrar_log(
                    self.usuario, LogAtividade.Acao.EMAIL_ALTERADO, self.ip_origem,
                    alvo_tipo='usuario', alvo_id=self.usuario.id,
                    resumo={'antes': mascarar_email(email_antigo or ''), 'depois': mascarar_email(email_novo)},
                )
        except (IntegrityError, TrocaEmailPendente.DoesNotExist):
            self.usuario.email = email_antigo
            TrocaEmailPendente.objects.filter(pk=pendente.pk).delete()
            self._log(LogAtividade.Acao.EMAIL_ALTERACAO_RECUSADA, email_novo, {'motivo': 'email_em_uso'})
            raise ErroTrocaEmail('Esse email não está mais disponível. Escolha outro.', status=409)

        if email_antigo:
            try:
                NotificacaoService().enviar_aviso_email_alterado(
                    email_antigo, self.usuario.apelido, mascarar_email(email_novo),
                )
            except Exception:
                logger.exception('Falha ao enviar aviso de troca de email')
                registrar_log(
                    self.usuario, LogAtividade.Acao.EMAIL_ALTERADO_AVISO_FALHOU, self.ip_origem,
                    alvo_tipo='usuario', alvo_id=self.usuario.id, resumo={'destino': mascarar_email(email_antigo)},
                )
        return self.usuario

    def _encerrar_pendencias(self, email_antigo):
        agora = timezone.now()
        Token.objects.filter(usuario=self.usuario).exclude(pk=self.token_atual.pk).delete()
        CodigoAutenticacao.objects.filter(usuario=self.usuario, usado_em__isnull=True).update(expira_em=agora)
        solicitacoes = Q(usuario=self.usuario)
        if email_antigo:
            solicitacoes |= Q(email=email_antigo)
        SolicitacaoRedefinicaoSenha.objects.filter(solicitacoes, usado_em__isnull=True).update(usado_em=agora)

    def _codigo_errado(self, pendente):
        pendente.tentativas += 1
        esgotou = pendente.tentativas >= TrocaEmailPendente.MAXIMO_TENTATIVAS
        if esgotou:
            TrocaEmailPendente.objects.filter(pk=pendente.pk).delete()
        else:
            pendente.save(update_fields=['tentativas'])
        self._log(
            LogAtividade.Acao.EMAIL_ALTERACAO_CODIGO_INVALIDO, pendente.email_novo,
            {'tentativas': pendente.tentativas, 'troca_invalidada': esgotou},
        )
        if esgotou:
            raise ErroTrocaEmail('Você errou o código muitas vezes. Peça um novo código.', status=410)
        raise ErroTrocaEmail('Código inválido. Tente novamente.')

    def _log(self, acao, email_novo, extra=None):
        registrar_log(
            self.usuario, acao, self.ip_origem, alvo_tipo='usuario', alvo_id=self.usuario.id,
            resumo={'destino': mascarar_email(email_novo), **(extra or {})},
        )
