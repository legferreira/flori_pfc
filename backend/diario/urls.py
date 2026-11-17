from django.urls import path

from . import views

urlpatterns = [
    path('diario', views.DiarioView.as_view(), name='diario'),
    path('diario/situacao', views.SituacaoView.as_view(), name='diario_situacao'),
    path('diario/resumo', views.ResumoView.as_view(), name='diario_resumo'),
    path('diario/<str:dia>', views.DiaView.as_view(), name='diario_dia'),
]
