from flori_backend.api import ViewAutenticada, erro, ler_json, resposta_json

from . import serializers
from .services import (
    ConcluirCard, ConsultarCertificado, ConsultarDashboard, ConsultarExtras, ConsultarQuiz, ConsultarTrilha, EnviarQuiz,
    ErroTrilha, IniciarQuiz,
)

MENSAGEM_ADMIN_TRILHA = 'O perfil admin só visualiza a trilha, nada é registrado'
MENSAGEM_ADMIN_DASHBOARD = 'O perfil admin não tem a página Minha evolução, use o Dashboard administrativo'


class ViewTrilha(ViewAutenticada):
    exige_consentimento = True
    bloqueado_para_admin = ()
    mensagem_admin = MENSAGEM_ADMIN_TRILHA

    def autorizar(self, request):
        if request.method in self.bloqueado_para_admin and request.usuario.is_admin:
            return erro(self.mensagem_admin, status=403)
        return super().autorizar(request)

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except ErroTrilha as e:
            return erro(e.mensagem, status=e.status, campos=e.campos)


class TrilhaView(ViewTrilha):
    def get(self, request):
        return resposta_json(serializers.trilha_completa(ConsultarTrilha(request.usuario).executar()))


class ExtrasView(ViewTrilha):
    def get(self, request):
        return resposta_json(serializers.extras(ConsultarExtras().executar()))


class ConcluirCardView(ViewTrilha):
    bloqueado_para_admin = ('POST',)

    def post(self, request, card_id):
        progresso = ConcluirCard(request.usuario, card_id).executar()
        return resposta_json({'card_id': str(progresso.card_id), 'concluido_em': progresso.concluido_em.isoformat()})


class QuizView(ViewTrilha):
    bloqueado_para_admin = ('POST',)

    def get(self, request):
        _, tentativa, perguntas = ConsultarQuiz(request.usuario).executar()
        return resposta_json(serializers.quiz(tentativa, perguntas))

    def post(self, request):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')
        return resposta_json(serializers.resultado_quiz(EnviarQuiz(request.usuario, dados).executar()))


class TentativaQuizView(ViewTrilha):
    bloqueado_para_admin = ('POST',)

    def post(self, request):
        _, tentativa, itens = IniciarQuiz(request.usuario).executar()
        return resposta_json(serializers.quiz(tentativa, [item.pergunta for item in itens]))


class CertificadoView(ViewTrilha):
    bloqueado_para_admin = ('GET',)

    def get(self, request):
        trilha, certificado = ConsultarCertificado(request.usuario).executar()
        return resposta_json(serializers.certificado(certificado, trilha))


class DashboardView(ViewTrilha):
    bloqueado_para_admin = ('GET',)
    mensagem_admin = MENSAGEM_ADMIN_DASHBOARD

    def get(self, request):
        return resposta_json(ConsultarDashboard(request.usuario).executar())
