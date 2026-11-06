import json

from django.conf import settings
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt


def resposta_json(dados, status=200):
    return JsonResponse(dados, status=status, json_dumps_params={'ensure_ascii': False})


def erro(mensagem, status=400):
    return resposta_json({'mensagem': mensagem}, status=status)


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


def usuario_autenticado(request):
    from users.models import Token

    cabecalho = request.META.get('HTTP_AUTHORIZATION', '')
    if not cabecalho.startswith('Bearer '):
        return None
    chave = cabecalho.removeprefix('Bearer ').strip()
    token = Token.objects.filter(chave=chave).select_related('usuario').first()
    return token.usuario if token else None


class ViewAutenticada(View):
    exige_consentimento = False

    @classmethod
    def as_view(cls, **initkwargs):
        return csrf_exempt(super().as_view(**initkwargs))

    def dispatch(self, request, *args, **kwargs):
        usuario = usuario_autenticado(request)
        if usuario is None:
            return erro('Não autenticada. Faça login novamente.', status=401)
        if self.exige_consentimento and usuario.tem_consentimento_revogado():
            return erro('Você revogou seu consentimento. Reative em Perfil para continuar.', status=403)
        request.usuario = usuario
        return super().dispatch(request, *args, **kwargs)
