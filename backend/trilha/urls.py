from django.urls import path

from . import views

urlpatterns = [
    path('trilha', views.TrilhaView.as_view(), name='trilha'),
    path('trilha/extras', views.ExtrasView.as_view(), name='trilha_extras'),
    path('trilha/cards/<uuid:card_id>/concluir', views.ConcluirCardView.as_view(), name='concluir_card'),
    path('trilha/quiz', views.QuizView.as_view(), name='quiz'),
    path('trilha/quiz/tentativas', views.TentativaQuizView.as_view(), name='tentativa_quiz'),
    path('trilha/certificado', views.CertificadoView.as_view(), name='certificado'),
    path('dashboard', views.DashboardView.as_view(), name='dashboard'),
]
