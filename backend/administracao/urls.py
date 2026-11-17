from django.urls import path

from . import views

urlpatterns = [
    path('admin/dashboard', views.DashboardAdminView.as_view(), name='admin_dashboard'),
    path('admin/users', views.UsersAdminView.as_view(), name='admin_users'),
    path('admin/users/<uuid:usuario_id>/excluir', views.ExcluirUserAdminView.as_view(), name='admin_excluir_user'),
    path('admin/conteudo/quiz/resumo', views.ResumoQuizAdminView.as_view(), name='admin_resumo_quiz'),
    path('admin/conteudo/<str:recurso>', views.ConteudoAdminView.as_view(), name='admin_conteudo'),
    path('admin/conteudo/<str:recurso>/<uuid:item_id>', views.ItemConteudoAdminView.as_view(), name='admin_item_conteudo'),
    path(
        'admin/conteudo/<str:recurso>/<uuid:item_id>/<str:acao>', views.AcaoConteudoAdminView.as_view(),
        name='admin_acao_conteudo',
    ),
]
