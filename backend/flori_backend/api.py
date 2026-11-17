import json

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt


def resposta_json(dados, status=200):
    return JsonResponse(dados, status=status, json_dumps_params={'ensure_ascii': False})


def erro(mensagem, status=400, campos=None, codigo=None):
    corpo = {'mensagem': mensagem}
    if campos:
        corpo['campos'] = campos
    if codigo:
        corpo['codigo'] = codigo
    return resposta_json(corpo, status=status)


def ler_json(request):
    try:
        dados = json.loads(request.body)
    except ValueError:
        return None
    return dados if isinstance(dados, dict) else None


def ip_do_cliente(request):
    if getattr(settings, 'CONFIA_EM_X_FORWARDED_FOR', False):
        encaminhado = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if encaminhado:
            return encaminhado.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def momento_iso(momento):
    return timezone.localtime(momento).isoformat() if momento else None


def momento_exibicao(momento):
    return timezone.localtime(momento).strftime('%d/%m/%Y %H:%M:%S') if momento else None


def token_autenticado(request):
    from users.models import Token

    cabecalho = request.META.get('HTTP_AUTHORIZATION', '')
    if not cabecalho.startswith('Bearer '):
        return None
    chave = cabecalho.removeprefix('Bearer ').strip()
    return Token.objects.filter(chave=chave, usuario__ativo=True).select_related('usuario').first()


class ViewAutenticada(View):
    exige_consentimento = False

    @classmethod
    def as_view(cls, **initkwargs):
        return csrf_exempt(super().as_view(**initkwargs))

    def dispatch(self, request, *args, **kwargs):
        token = token_autenticado(request)
        if token is None:
            return erro('Não autenticada. Faça login novamente.', status=401)
        request.token = token
        request.usuario = token.usuario
        negado = self.autorizar(request)
        if negado is not None:
            return negado
        return super().dispatch(request, *args, **kwargs)

    def autorizar(self, request):
        if self.exige_consentimento and request.usuario.tem_consentimento_revogado():
            return erro('Você revogou seu consentimento. Reative em Perfil para continuar.', status=403)
        return None


class ViewAdmin(ViewAutenticada):
    def autorizar(self, request):
        from users.auditoria import registrar_log_admin
        from users.models import LogAtividade, Usuario

        if request.usuario.perfil == Usuario.Perfil.ADMIN:
            return None
        registrar_log_admin(
            request.usuario, LogAtividade.Acao.ADMIN_ACESSO_NEGADO, 'rota', request.path[:64],
            {'metodo': request.method}, ip_do_cliente(request),
        )
        return erro('Acesso restrito a admin.', status=403)

    def dispatch(self, request, *args, **kwargs):
        from trilha.services import ErroTrilha
        from users.models import AdminProtegido
        from users.services import ErroPerfil, ErroServico

        try:
            return super().dispatch(request, *args, **kwargs)
        except (ErroServico, ErroPerfil, ErroTrilha) as e:
            return erro(e.mensagem, status=e.status, campos=getattr(e, 'campos', None))
        except AdminProtegido as e:
            return erro(e.mensagem, status=403)
