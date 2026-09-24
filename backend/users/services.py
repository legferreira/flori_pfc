
from datetime import date, timedelta
import logging
import math
import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone


from django.db import IntegrityError, transaction


from .models import (
    CodigoAutenticacao, Consentimento, LogAtividade, SolicitacaoRedefinicaoSenha, Token, Usuario,
)
from .notificacoes import ErroNotificacao, NotificacaoService

logger = logging.getLogger(__name__)


VERSAO_TERMOS_USO = '1.0'
VERSAO_POLITICA_PRIVACIDADE = '1.0'

TAMANHO_MAXIMO_NOME = 100
TAMANHO_MAXIMO_SOBRENOME = 100
TAMANHO_MAXIMO_APELIDO = 50


class ErroCadastro(Exception):
    def __init__(self, mensagem, status=400):
        super().__init__(mensagem)  # inicializa a Exception padrão do Python com a mensagem
        self.mensagem = mensagem    # guarda a mensagem como atributo, pra views.py ler via e.mensagem
        self.status = status        # guarda o status HTTP como atributo, pra views.py ler via e.status


class CadastroUsuario:
    """Cadastra uma usuária a partir dos dados crus da requisição.
    Cada regra vive em seu próprio método; `executar()` apenas define a ordem.
    """

    
    VIA_GOOGLE = False


    def __init__(self, dados, ip_origem=None):
        self._dados = dados          # dict original, guardado para os métodos usarem .get()
        self.ip_origem = ip_origem   # IP calculado por views.ip_do_cliente(), repassado ao Consentimento
        self.nome = self._capitalizar(self._texto('nome'))
        self.sobrenome = self._capitalizar(self._texto('sobrenome'))
        self.apelido = self._texto('apelido')
        self.email = self._texto('email').lower() or None       # normaliza para minúsculas; string vazia vira None
        self.celular = self._texto('celular') or None            # string vazia vira None
        self.senha = self._dados.get('senha') if isinstance(self._dados.get('senha'), str) else ''
        self.termos_aceitos = bool(self._dados.get('termos_aceitos'))
        self.data_nascimento = None 


# etapas do cadastro, chamando os metodos de validacao e persistencia

    def executar(self):
        self._validar_identificacao()
        self._validar_nascimento()
        self._validar_contato()
        self._validar_senha()
        self._validar_consentimento()
        return self._persistir()

    # lê um campo do dict self._dados e devolve a versão "limpa" (sem espaços
    # nas pontas). Se o valor não for string (ausente, None, número...), devolve ''.

    def _texto(self, campo):
        valor = self._dados.get(campo)
        return valor.strip() if isinstance(valor, str) else ''

    # Normaliza nome/sobrenome pra "Primeira Maiúscula" independente de como a
    # pessoa digitou 
    def _capitalizar(self, texto):
        return ' '.join(palavra[:1].upper() + palavra[1:].lower() for palavra in texto.split())

    # regras de negócio  
    # Aqui separei as responsabilidades


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

    def _validar_senha(self):
        if len(self.senha) < Usuario.TAMANHO_MINIMO_SENHA:
            raise ErroCadastro(
                f'A senha precisa ter pelo menos {Usuario.TAMANHO_MINIMO_SENHA} caracteres.'
            )

    def _validar_consentimento(self):
        if not self.termos_aceitos:
            raise ErroCadastro('É necessário aceitar os termos de uso.')

    # persistência aqui estou salvando as informacoes}_persistir() é a última etapa do executar(): é onde o cadastro e salvo no banco de dados#
    
    def _persistir(self):
        usuario = Usuario(
            nome=self.nome,
            sobrenome=self.sobrenome,
            apelido=self.apelido or self.nome,
            data_nascimento=self.data_nascimento,
            email=self.email,
            celular=self.celular,
        )
        # Transforma a senha em texto puro (self.senha) em hash e grava em
        # usuario.senha_hash (CadastroUsuarioGoogle sobrescreve: conta sem senha).
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


        if usuario.email:
            try:
                NotificacaoService().enviar_confirmacao_cadastro(usuario, via_google=self.VIA_GOOGLE)
            except Exception:
                logger.exception('Falha ao enviar e-mail de confirmação de cadastro')

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

    def _erro_de_duplicidade(self):
        """O banco recusou por UNIQUE — descobre qual contato já estava em uso."""
        if self.email and Usuario.objects.filter(email=self.email).exists():
            return ErroCadastro('Esse e-mail já está em uso.', status=409)
        if self.celular and Usuario.objects.filter(celular=self.celular).exists():
            return ErroCadastro('Esse celular já está em uso.', status=409)
        return ErroCadastro('Não foi possível concluir o cadastro.', status=409)



class ErroLogin(Exception):
    def __init__(self, mensagem, status=401):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


def iniciar_sessao(usuario, ip_origem=None, acao=LogAtividade.Acao.LOGIN_SUCESSO):
    """Emite o Token de sessão e registra o login — último passo de qualquer login bem-sucedido."""
    token = Token.objects.create(usuario=usuario)
    LogAtividade.objects.create(
        usuario=usuario,
        acao=acao,
        ip_origem=ip_origem,
    )
    return token


class LoginUsuario:
    """Autentica uma usuária por contato (e-mail ou celular) + senha.

    Com e-mail cadastrado, a senha certa NÃO libera o login ainda: envia um
    código de verificação (2FA) e devolve o desafio, o login termina em
    VerificarCodigoAutenticacao. Sem e-mail (conta só com celular) não há
    para onde mandar o código, então emite o Token direto.
    """

    def __init__(self, dados, ip_origem=None):
        self._dados = dados
        self.ip_origem = ip_origem
        self.contato = self._texto('contato') or self._texto('email') or self._texto('celular')
        self.senha = self._dados.get('senha') if isinstance(self._dados.get('senha'), str) else ''

    def _texto(self, campo):
        valor = self._dados.get(campo)
        return valor.strip() if isinstance(valor, str) else ''

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


class ResultadoLogin:
    """O que LoginUsuario devolve: OU o token (login concluído) OU o desafio (falta o código)."""

    def __init__(self, usuario, token=None, desafio=None):
        self.usuario = usuario
        self.token = token
        self.desafio = desafio

    @property
    def requer_codigo(self):
        return self.desafio is not None


def mascarar_email(email):
    """'rafael@gmail.com' -> 'ra****@gmail.com' — mostra para onde foi o código sem expor o e-mail inteiro."""
    nome, _, dominio = email.partition('@')
    visivel = nome[:2] if len(nome) > 2 else nome[:1]
    return f'{visivel}{"*" * max(len(nome) - len(visivel), 1)}@{dominio}'


class EnviarCodigoAutenticacao:
    """Gera o código de 6 dígitos, grava só o hash e envia por e-mail. Devolve o desafio."""

    def __init__(self, usuario, ip_origem=None):
        self.usuario = usuario
        self.ip_origem = ip_origem

    def executar(self):
        agora = timezone.now()
        codigo = f'{secrets.randbelow(10 ** 6):06d}'
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
    """Segunda etapa do login: confere o código digitado e, se bater, emite o Token."""

    MENSAGEM_CODIGO_INVALIDO = 'Código inválido. Tente novamente.'
    MENSAGEM_EXPIRADO = 'Este código expirou. Faça login de novo para receber um novo código.'

    def __init__(self, dados, ip_origem=None):
        self.ip_origem = ip_origem
        desafio = dados.get('desafio')
        codigo = dados.get('codigo')
        self.desafio = desafio.strip() if isinstance(desafio, str) else ''
        self.codigo = ''.join(c for c in codigo if c.isdigit()) if isinstance(codigo, str) else ''

    def executar(self):
        if not self.desafio:
            raise ErroLogin(self.MENSAGEM_EXPIRADO, status=410)
        if len(self.codigo) != 6:
            raise ErroLogin('Digite os 6 números do código.', status=400)

        agora = timezone.now()
        erro = None
        with transaction.atomic():
            
            registro = (
                CodigoAutenticacao.objects
                .select_for_update()
                .select_related('usuario')
                .filter(desafio_hash=CodigoAutenticacao.gerar_hash_desafio(self.desafio))
                .first()
            )
            if not registro or not registro.pode_ser_usado(agora):
                erro = ErroLogin(self.MENSAGEM_EXPIRADO, status=410)
            elif not registro.confere(self.codigo):
                registro.tentativas += 1
                registro.save(update_fields=['tentativas'])
                LogAtividade.objects.create(
                    usuario=registro.usuario,
                    acao=LogAtividade.Acao.CODIGO_2FA_INVALIDO,
                    ip_origem=self.ip_origem,
                )
                if registro.tentativas >= CodigoAutenticacao.MAXIMO_TENTATIVAS:
                    erro = ErroLogin(
                        'Você errou o código muitas vezes. Faça login de novo para receber um novo código.',
                        status=410,
                    )
                else:
                    erro = ErroLogin(self.MENSAGEM_CODIGO_INVALIDO, status=400)
            else:
                registro.usado_em = agora
                registro.save(update_fields=['usado_em'])
                token = iniciar_sessao(registro.usuario, self.ip_origem)

        if erro:
            raise erro
        return registro.usuario, token


def verificar_token_google(valor):
    """Verifica o ID token do Firebase e devolve o perfil Google: {'email', 'nome', 'sobrenome', 'foto'}.

    O token é VERIFICADO com as chaves públicas do Google (assinatura,
    validade e se foi emitido para o nosso projeto Firebase) — nunca
    confiamos no e-mail que o front-end diz ter. Lança ErroLogin se não passar.
    """
    # Import local: google-auth só é necessário para os fluxos com Google.
    from google.auth import exceptions as google_exceptions
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    id_token_google = valor.strip() if isinstance(valor, str) else ''
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

    # Só aceita login feito pelo provedor Google e com e-mail confirmado
    # pelo Google — e-mail não verificado poderia ser de outra pessoa.
    provedor = dados.get('firebase', {}).get('sign_in_provider')
    email = (dados.get('email') or '').strip().lower()
    if provedor != 'google.com' or not email or not dados.get('email_verified'):
        raise ErroLogin('Não foi possível confirmar seu e-mail com o Google.', status=401)

    # O token do Firebase traz só o nome completo ('name'): a primeira palavra
    # vira o nome e o resto o sobrenome — só sugestão, a pessoa pode corrigir.
    nome, _, sobrenome = (dados.get('name') or '').strip().partition(' ')
    return {
        'email': email, 'nome': nome, 'sobrenome': sobrenome.strip(),
        'foto': dados.get('picture') or None,
    }


class LoginGoogle:
    """Botão "Continuar com Google" (Firebase Authentication): entra ou leva ao cadastro.

    Com conta existente para o e-mail do Google: emite o Token e pronto.
    Sem conta: devolve o perfil do Google para o front-end abrir a tela
    "Complete seu cadastro" (ver CadastroUsuarioGoogle).
    Não pede o código por e-mail (2FA): a conta Google já tem a própria
    proteção, e o login por ela prova posse do e-mail.
    """

    def __init__(self, dados, ip_origem=None):
        self.ip_origem = ip_origem
        self.id_token = dados.get('id_token')

    def executar(self):
        """Devolve (usuario, token, None) se entrou, ou (None, None, perfil) se falta o cadastro."""
        perfil = verificar_token_google(self.id_token)

        usuario = Usuario.objects.filter(email=perfil['email']).first()
        if not usuario:
            return None, None, perfil

        # Mantém a foto em dia (a pessoa pode ter trocado a foto no Google).
        if perfil['foto'] and usuario.foto_url != perfil['foto']:
            usuario.foto_url = perfil['foto']
            usuario.save(update_fields=['foto_url'])

        token = iniciar_sessao(usuario, self.ip_origem, acao=LogAtividade.Acao.LOGIN_GOOGLE)
        return usuario, token, None


class CadastroUsuarioGoogle(CadastroUsuario):
    """Cadastro pelo Google: mesmas regras do CadastroUsuario, menos a senha.

    O e-mail vem do token verificado (não do que o front-end manda) e a conta
    nasce sem senha. Continuam obrigatórios: nome, sobrenome, apelido, data
    de nascimento (idade mínima) e aceite dos termos (LGPD) — o que o Google
    não fornece e a tela "Complete seu cadastro" pede.
    """

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
        pass  # conta sem senha — ver Usuario.definir_sem_senha

    def _definir_senha(self, usuario):
        usuario.definir_sem_senha()


class ErroRedefinicaoSenha(Exception):
    def __init__(self, mensagem, status=400, espera_segundos=0):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status
        self.espera_segundos = espera_segundos


class SolicitarRedefinicaoSenha:
    """Fluxo de "esqueci a senha": gera um token provisório e envia por e-mail.

    Entre um pedido e outro para o mesmo e-mail a espera dobra: 2 min depois
    do 1º, 4 depois do 2º, 8 depois do 3º... A contagem zera quando o e-mail
    fica JANELA_CONTAGEM sem pedidos.
    """

    ESPERA_BASE_MINUTOS = 2
    ESPERA_MAXIMA_MINUTOS = 24 * 60
    JANELA_CONTAGEM = timedelta(hours=24)
    VALIDADE_TOKEN = timedelta(minutes=30)

    def __init__(self, dados, ip_origem=None):
        self._dados = dados
        self.ip_origem = ip_origem
        valor = dados.get('email')
        self.email = valor.strip().lower() if isinstance(valor, str) else ''

    @classmethod
    def espera_apos(cls, quantidade_pedidos):
        """Espera exigida depois do N-ésimo pedido: 2, 4, 8, 16... minutos (com teto)."""
        minutos = cls.ESPERA_BASE_MINUTOS * 2 ** (quantidade_pedidos - 1)
        return timedelta(minutes=min(minutos, cls.ESPERA_MAXIMA_MINUTOS))

    def executar(self):
        """Devolve quantos segundos faltam até o próximo pedido ser aceito."""
        self._validar_email()
        agora = timezone.now()

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

        usuario = Usuario.objects.filter(email=self.email).first()
        token = secrets.token_urlsafe(32) if usuario else None

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

        if usuario:
            link = f'{settings.FRONTEND_URL}/redefinir-senha.html?token={token}'
            try:
                NotificacaoService().enviar_recuperacao_senha(
                    usuario, link, validade_minutos=int(self.VALIDADE_TOKEN.total_seconds() // 60),
                )
            except Exception:
                logger.exception('Falha ao enviar e-mail de redefinição de senha')

        return int(self.espera_apos(quantidade + 1).total_seconds())

    def _validar_email(self):
        try:
            validate_email(self.email)
        except ValidationError:
            raise ErroRedefinicaoSenha('Informe um e-mail válido.')


class ConfirmarRedefinicaoSenha:
    """Troca a senha usando o token provisório recebido por e-mail.

    O token vale uma vez só. Ao trocar a senha: invalida os outros links
    pendentes da usuária e encerra as sessões abertas (apaga os Tokens de
    login), para o caso de alguém ter entrado na conta com a senha antiga.
    """

    MENSAGEM_LINK_INVALIDO = 'Este link é inválido ou expirou. Peça um novo em "Esqueci minha senha".'

    def __init__(self, dados, ip_origem=None):
        self._dados = dados
        self.ip_origem = ip_origem
        token = dados.get('token')
        self.token = token.strip() if isinstance(token, str) else ''
        self.senha = dados.get('senha') if isinstance(dados.get('senha'), str) else ''

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