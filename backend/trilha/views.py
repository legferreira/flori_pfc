from flori_backend.api import ViewAutenticada, erro, ler_json, resposta_json

from . import serializers
from .services import (
    ConcluirCard, ConsultarCertificado, ConsultarDashboard, ConsultarQuiz, ConsultarTrilha, EnviarQuiz, ErroTrilha,
)


class ViewTrilha(ViewAutenticada):
    exige_consentimento = True

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except ErroTrilha as e:
            return erro(e.mensagem, status=e.status)


class TrilhaView(ViewTrilha):
    def get(self, request):
        return resposta_json(serializers.trilha_completa(ConsultarTrilha(request.usuario).executar()))


class ConcluirCardView(ViewTrilha):
    def post(self, request, card_id):
        progresso = ConcluirCard(request.usuario, card_id).executar()
        return resposta_json({'card_id': str(progresso.card_id), 'concluido_em': progresso.concluido_em.isoformat()})


class QuizView(ViewTrilha):
    def get(self, request):
        trilha, perguntas = ConsultarQuiz(request.usuario).executar()
        return resposta_json(serializers.quiz(trilha, perguntas))

    def post(self, request):
        dados = ler_json(request)
        if dados is None:
            return erro('JSON inválido.')
        return resposta_json(serializers.resultado_quiz(EnviarQuiz(request.usuario, dados).executar()))


class CertificadoView(ViewTrilha):
    def get(self, request):
        trilha, certificado = ConsultarCertificado(request.usuario).executar()
        return resposta_json(serializers.certificado(certificado, trilha))


class DashboardView(ViewTrilha):
    def get(self, request):
        return resposta_json(ConsultarDashboard(request.usuario).executar())
