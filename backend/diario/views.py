from django.http import HttpResponse

from flori_backend.api import ViewAutenticada, erro, ler_json, resposta_json

from . import constantes
from .services import (
    ApagarDiario, ConsultarMes, DefinirSituacao, ErroDiario, ExcluirDia, RegistrarDia, ResumoCiclo, estado_da_situacao,
)

MENSAGEM_CONSENTIMENTO_GERAL = 'Você revogou seu consentimento. Reative em Perfil para continuar.'


class ViewDiario(ViewAutenticada):
    def autorizar(self, request):
        if request.usuario.is_admin:
            return erro(constantes.MENSAGEM_PERFIL_ADMIN, status=403, codigo='perfil_admin')
        if request.method != 'DELETE' and request.usuario.tem_consentimento_revogado():
            return erro(MENSAGEM_CONSENTIMENTO_GERAL, status=403)
        return None

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except ErroDiario as e:
            return erro(e.mensagem, status=e.status, campos=e.campos, codigo=e.codigo)


class SituacaoView(ViewDiario):
    def get(self, request):
        return resposta_json(estado_da_situacao(request.usuario))

    def put(self, request):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')
        return resposta_json(DefinirSituacao(request.usuario, dados).executar())


class DiarioView(ViewDiario):
    def get(self, request):
        return resposta_json(ConsultarMes(request.usuario, request.GET.get('mes')).executar())

    def delete(self, request):
        dados = ler_json(request)
        return resposta_json({'apagados': ApagarDiario(request.usuario, dados).executar()})


class DiaView(ViewDiario):
    def put(self, request, dia):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')
        return resposta_json(RegistrarDia(request.usuario, dia, dados).executar())

    def delete(self, request, dia):
        ExcluirDia(request.usuario, dia).executar()
        return HttpResponse(status=204)


class ResumoView(ViewDiario):
    def get(self, request):
        return resposta_json(ResumoCiclo(request.usuario).executar())
