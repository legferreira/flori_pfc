import json

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import CodigoAutenticacao, LogAtividade, Token
from .services import (
    CadastroUsuario, CadastroUsuarioGoogle, ConfirmarRedefinicaoSenha, ErroCadastro,
    ErroLogin, ErroRedefinicaoSenha, LoginGoogle, LoginUsuario, SolicitarRedefinicaoSenha,
    VerificarCodigoAutenticacao, iniciar_sessao, mascarar_email,
)


def resposta_json(dados, status=200):
    return JsonResponse(dados, status=status, json_dumps_params={'ensure_ascii': False})


def erro(mensagem, status=400):
    return resposta_json({'mensagem': mensagem}, status=status)


def ip_do_cliente(request):
    """IP para o registro de consentimento.
    """
    if getattr(settings, 'CONFIA_EM_X_FORWARDED_FOR', False):
        encaminhado = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if encaminhado:
            return encaminhado.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def usuario_autenticado(request):
    """Confere o token enviado no header Authorization e devolve o Usuario dono dele.
    """
    cabecalho = request.META.get('HTTP_AUTHORIZATION', '')
    if not cabecalho.startswith('Bearer '):
        return None
    chave = cabecalho.removeprefix('Bearer ').strip()
    token = Token.objects.filter(chave=chave).select_related('usuario').first()
    return token.usuario if token else None


@method_decorator(csrf_exempt, name='dispatch')
class CadastroUsuarioView(View):
    """View HTTP para o endpoint POST /api/usuarios."""

    def post(self, request):
        try:
            dados = json.loads(request.body)
        except ValueError:
            return erro('JSON inválido.')

        if not isinstance(dados, dict):
            return erro('JSON inválido.')

        try:
            usuario = CadastroUsuario(dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroCadastro as e:
            return erro(e.mensagem, status=e.status)

        return resposta_json({'id': usuario.id, 'apelido': usuario.apelido}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class CadastroGoogleView(View):
    """View HTTP para o endpoint POST /api/usuarios/google.

    Recebe {'id_token', 'nome', 'sobrenome', 'apelido', 'data_nascimento',
    'termos_aceitos'}. Cria a conta (e-mail vem do Google) e já entra:
    devolve o token de sessão, igual a um login.
    """

    def post(self, request):
        try:
            dados = json.loads(request.body)
        except ValueError:
            return erro('JSON inválido.')

        if not isinstance(dados, dict):
            return erro('JSON inválido.')

        ip = ip_do_cliente(request)
        try:
            usuario = CadastroUsuarioGoogle(dados, ip_origem=ip).executar()
        except ErroCadastro as e:
            return erro(e.mensagem, status=e.status)

        token = iniciar_sessao(usuario, ip, acao=LogAtividade.Acao.LOGIN_GOOGLE)
        return resposta_sessao(usuario, token, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class LoginUsuarioView(View):
    """View HTTP para o endpoint POST /api/login.

    Autentica por contato (e-mail ou celular) + senha. Duas respostas possíveis:
    - {'requer_codigo': true, 'desafio': ...}: código 2FA enviado por e-mail;
      o login termina em POST /api/login/verificar.
    - {'requer_codigo': false, 'token': ...}: conta sem e-mail, login concluído.
    O token é o que o front-end reenvia no header Authorization depois.
    """

    def post(self, request):
        try:
            dados = json.loads(request.body)
        except ValueError:
            return erro('JSON inválido.')

        if not isinstance(dados, dict):
            return erro('JSON inválido.')

        try:
            resultado = LoginUsuario(dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroLogin as e:
            return erro(e.mensagem, status=e.status)

        if resultado.requer_codigo:
            return resposta_json({
                'requer_codigo': True,
                'desafio': resultado.desafio,
                'email_mascarado': mascarar_email(resultado.usuario.email),
                'validade_minutos': CodigoAutenticacao.VALIDADE_MINUTOS,
            }, status=200)

        return resposta_sessao(resultado.usuario, resultado.token)


def resposta_sessao(usuario, token, status=200):
    """Resposta de login concluído igual em todo login (senha, código, Google) e no cadastro pelo Google."""
    return resposta_json({
        'requer_codigo': False,
        'token': token.chave,
        'id': usuario.id,
        'apelido': usuario.apelido,
    }, status=status)


@method_decorator(csrf_exempt, name='dispatch')
class VerificarCodigoView(View):
    """View HTTP para o endpoint POST /api/login/verificar — segunda etapa do login (2FA).
    Recebe {'desafio': ..., 'codigo': '123456'}. 400 = código errado (pode
    tentar de novo); 410 = expirado/tentativas esgotadas (precisa logar de novo).
    """

    def post(self, request):
        try:
            dados = json.loads(request.body)
        except ValueError:
            return erro('JSON inválido.')

        if not isinstance(dados, dict):
            return erro('JSON inválido.')

        try:
            usuario, token = VerificarCodigoAutenticacao(dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroLogin as e:
            return erro(e.mensagem, status=e.status)

        return resposta_sessao(usuario, token)


@method_decorator(csrf_exempt, name='dispatch')
class LoginGoogleView(View):
    """View HTTP para o endpoint POST /api/login/google.
    Recebe {'id_token': ...} (o ID token do Firebase depois do popup do Google).
    Sem conta para o e-mail: {'cadastro_necessario': true, 'email', 'nome',
    'sobrenome'} — o front-end abre "Complete seu cadastro" (POST /api/usuarios/google).
    """

    def post(self, request):
        try:
            dados = json.loads(request.body)
        except ValueError:
            return erro('JSON inválido.')

        if not isinstance(dados, dict):
            return erro('JSON inválido.')

        try:
            usuario, token, perfil = LoginGoogle(dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroLogin as e:
            return erro(e.mensagem, status=e.status)

        if perfil:
            return resposta_json({'cadastro_necessario': True, **perfil}, status=200)
        return resposta_sessao(usuario, token)


@method_decorator(csrf_exempt, name='dispatch')
class ResetarSenhaView(View):
    """View HTTP para o endpoint POST /api/resetar-senha ("esqueci a senha").
    Responde igual exista ou não uma conta com o e-mail — não revela quem
    está cadastrada. 429 quando ainda está no intervalo de espera.
    """

    def post(self, request):
        try:
            dados = json.loads(request.body)
        except ValueError:
            return erro('JSON inválido.')

        if not isinstance(dados, dict):
            return erro('JSON inválido.')

        try:
            espera = SolicitarRedefinicaoSenha(dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroRedefinicaoSenha as e:
            return resposta_json(
                {'mensagem': e.mensagem, 'espera_segundos': e.espera_segundos},
                status=e.status,
            )

        return resposta_json({
            'mensagem': 'Se esse e-mail estiver cadastrado, você vai receber um link para criar uma nova senha.',
            'espera_segundos': espera,
        }, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class ConfirmarResetarSenhaView(View):
    """View HTTP para o endpoint POST /api/resetar-senha/confirmar.
    Recebe o token do link enviado por e-mail e a nova senha.
    """

    def post(self, request):
        try:
            dados = json.loads(request.body)
        except ValueError:
            return erro('JSON inválido.')

        if not isinstance(dados, dict):
            return erro('JSON inválido.')

        try:
            ConfirmarRedefinicaoSenha(dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroRedefinicaoSenha as e:
            return erro(e.mensagem, status=e.status)

        return resposta_json({'mensagem': 'Senha alterada! Agora é só entrar com a nova senha.'})


@method_decorator(csrf_exempt, name='dispatch')
class PerfilView(View):
    """View HTTP para o endpoint GET /api/perfil — exige token válido.
    Demonstra a camada de autorização: sem um token válido no header
    Authorization, ninguém acessa dado nenhum daqui, mesmo sabendo a URL.
    """

    def get(self, request):
        usuario = usuario_autenticado(request)
        if not usuario:
            return erro('Não autenticada. Faça login novamente.', status=401)

        return resposta_json({
            'id': usuario.id,
            'apelido': usuario.apelido,
            'nome': usuario.nome,
            'email': usuario.email,
            'foto_url': usuario.foto_url,
        })


@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(View):
    """View HTTP para o endpoint POST /api/logout — encerra a sessão.
    Apaga do banco o token enviado no header Authorization: depois disso ele
    não vale mais, mesmo que alguém tenha copiado. Só limpar o navegador
    deixaria o token válido no servidor.
    """

    def post(self, request):
        cabecalho = request.META.get('HTTP_AUTHORIZATION', '')
        chave = cabecalho.removeprefix('Bearer ').strip() if cabecalho.startswith('Bearer ') else ''
        token = Token.objects.filter(chave=chave).select_related('usuario').first() if chave else None
        if token:
            LogAtividade.objects.create(
                usuario=token.usuario, acao=LogAtividade.Acao.LOGOUT, ip_origem=ip_do_cliente(request),
            )
            token.delete()
        # 204 mesmo sem token válido: o objetivo (não estar logada) já foi atingido.
        return HttpResponse(status=204)