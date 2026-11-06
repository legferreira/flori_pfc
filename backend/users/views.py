from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from flori_backend.api import ViewAutenticada, erro, ip_do_cliente, ler_json, resposta_json

from .models import CodigoAutenticacao, LogAtividade, Token
from .services import (
    AlterarConsentimento, AtualizarPerfil, CadastroUsuario, CadastroUsuarioGoogle, ConfirmarRedefinicaoSenha,
    ErroCadastro, ErroLogin, ErroPerfil, ErroRedefinicaoSenha, LoginGoogle, LoginUsuario,
    SolicitarRedefinicaoSenha, VerificarCodigoAutenticacao, iniciar_sessao, mascarar_email,
)


def resposta_sessao(usuario, token, status=200):
    return resposta_json({
        'requer_codigo': False,
        'token': token.chave,
        'id': usuario.id,
        'apelido': usuario.apelido,
    }, status=status)


@method_decorator(csrf_exempt, name='dispatch')
class CadastroUsuarioView(View):
    def post(self, request):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')

        try:
            usuario = CadastroUsuario(dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroCadastro as e:
            return erro(e.mensagem, status=e.status)

        return resposta_json({'id': usuario.id, 'apelido': usuario.apelido}, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class CadastroGoogleView(View):
    def post(self, request):
        dados = ler_json(request)
        if dados is None:
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
    def post(self, request):
        dados = ler_json(request)
        if dados is None:
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


@method_decorator(csrf_exempt, name='dispatch')
class VerificarCodigoView(View):
    def post(self, request):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')

        try:
            usuario, token = VerificarCodigoAutenticacao(dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroLogin as e:
            return erro(e.mensagem, status=e.status)

        return resposta_sessao(usuario, token)


@method_decorator(csrf_exempt, name='dispatch')
class LoginGoogleView(View):
    def post(self, request):
        dados = ler_json(request)
        if dados is None:
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
    def post(self, request):
        dados = ler_json(request)
        if dados is None:
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
    def post(self, request):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')

        try:
            ConfirmarRedefinicaoSenha(dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroRedefinicaoSenha as e:
            return erro(e.mensagem, status=e.status)

        return resposta_json({'mensagem': 'Senha alterada! Agora é só entrar com a nova senha.'})


def dados_do_perfil(usuario):
    consentimentos = [
        {
            'tipo': c.tipo, 'rotulo': c.get_tipo_display(), 'aceito': c.aceito,
            'versao_documento': c.versao_documento, 'data': c.data_consentimento.isoformat(),
        }
        for c in usuario.consentimentos_atuais().values()
    ]
    return {
        'id': usuario.id,
        'apelido': usuario.apelido,
        'nome': usuario.nome,
        'sobrenome': usuario.sobrenome,
        'email': usuario.email,
        'celular': usuario.celular,
        'data_nascimento': usuario.data_nascimento,
        'foto_url': usuario.foto_url,
        'consentimentos': consentimentos,
    }


class PerfilView(ViewAutenticada):
    def get(self, request):
        return resposta_json(dados_do_perfil(request.usuario))

    def patch(self, request):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')

        try:
            usuario = AtualizarPerfil(request.usuario, dados).executar()
        except ErroPerfil as e:
            return erro(e.mensagem, status=e.status)

        return resposta_json(dados_do_perfil(usuario))


class ConsentimentoView(ViewAutenticada):
    def post(self, request):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')

        try:
            AlterarConsentimento(request.usuario, dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroPerfil as e:
            return erro(e.mensagem, status=e.status)

        return resposta_json(dados_do_perfil(request.usuario))


@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(View):
    def post(self, request):
        cabecalho = request.META.get('HTTP_AUTHORIZATION', '')
        chave = cabecalho.removeprefix('Bearer ').strip() if cabecalho.startswith('Bearer ') else ''
        token = Token.objects.filter(chave=chave).select_related('usuario').first() if chave else None
        if token:
            LogAtividade.objects.create(
                usuario=token.usuario, acao=LogAtividade.Acao.LOGOUT, ip_origem=ip_do_cliente(request),
            )
            token.delete()
        return HttpResponse(status=204)
