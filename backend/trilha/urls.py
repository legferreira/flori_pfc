from django.urls import path

from . import views

urlpatterns = [
    path('trilha', views.TrilhaView.as_view(), name='trilha'),
    path('trilha/cards/<uuid:card_id>/concluir', views.ConcluirCardView.as_view(), name='concluir_card'),
    path('trilha/quiz', views.QuizView.as_view(), name='quiz'),
    path('trilha/certificado', views.CertificadoView.as_view(), name='certificado'),
    path('dashboard', views.DashboardView.as_view(), name='dashboard'),
]
