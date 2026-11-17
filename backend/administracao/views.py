from django.http import HttpResponse

from flori_backend.api import ViewAdmin, erro, ip_do_cliente, ler_json, resposta_json

from .conteudo import ACOES_GET, ACOES_POST, gestor, resumo_do_quiz
from .services import ConsultarDashboardAdmin, ExcluirUsuarioAdmin, ListarUsuarios


class DashboardAdminView(ViewAdmin):
    def get(self, request):
        return resposta_json(ConsultarDashboardAdmin(request.usuario, request.GET, ip_do_cliente(request)).executar())


class UsersAdminView(ViewAdmin):
    def get(self, request):
        return resposta_json(ListarUsuarios(request.usuario, request.GET, ip_do_cliente(request)).executar())


class ExcluirUserAdminView(ViewAdmin):
    def post(self, request, usuario_id):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')
        ExcluirUsuarioAdmin(request.usuario, usuario_id, dados, ip_do_cliente(request)).executar()
        return HttpResponse(status=204)


class ConteudoAdminView(ViewAdmin):
    def get(self, request, recurso):
        return resposta_json({'itens': gestor(recurso, request.usuario).listar(request.GET)})

    def post(self, request, recurso):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')
        return resposta_json(gestor(recurso, request.usuario, ip_do_cliente(request)).criar(dados), status=201)


class ItemConteudoAdminView(ViewAdmin):
    def get(self, request, recurso, item_id):
        return resposta_json(gestor(recurso, request.usuario).detalhe(item_id))

    def put(self, request, recurso, item_id):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')
        return resposta_json(gestor(recurso, request.usuario, ip_do_cliente(request)).atualizar(item_id, dados))


class AcaoConteudoAdminView(ViewAdmin):
    def get(self, request, recurso, item_id, acao):
        if acao not in ACOES_GET:
            return erro('Ação não encontrada.', status=404)
        return resposta_json(getattr(gestor(recurso, request.usuario), acao)(item_id))

    def post(self, request, recurso, item_id, acao):
        if acao not in ACOES_POST:
            return erro('Ação não encontrada.', status=404)
        servico = gestor(recurso, request.usuario, ip_do_cliente(request))
        if acao == 'reordenar':
            dados = ler_json(request)
            if dados is None:
                return erro('JSON inválido.')
            return resposta_json(servico.reordenar(item_id, dados))
        return resposta_json(getattr(servico, acao)(item_id))


class ResumoQuizAdminView(ViewAdmin):
    def get(self, request):
        return resposta_json(resumo_do_quiz())
