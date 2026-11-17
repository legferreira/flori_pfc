from django.urls import path

from . import views

urlpatterns = [
    path('usuarios', views.CadastroUsuarioView.as_view(), name='cadastrar_usuario'),
    path('usuarios/google', views.CadastroGoogleView.as_view(), name='cadastrar_usuario_google'),
    path('login', views.LoginUsuarioView.as_view(), name='login_usuario'),
    path('login/verificar', views.VerificarCodigoView.as_view(), name='verificar_codigo'),
    path('login/google', views.LoginGoogleView.as_view(), name='login_google'),
    path('resetar-senha', views.ResetarSenhaView.as_view(), name='resetar_senha'),
    path('resetar-senha/confirmar', views.ConfirmarResetarSenhaView.as_view(), name='confirmar_resetar_senha'),
    path('perfil', views.PerfilView.as_view(), name='perfil'),
    path('perfil/consentimentos', views.ConsentimentoView.as_view(), name='consentimentos'),
    path('perfil/documentos/aceitar', views.AceitarDocumentosView.as_view(), name='aceitar_documentos'),
    path('perfil/email', views.TrocaEmailView.as_view(), name='trocar_email'),
    path('perfil/email/confirmar', views.ConfirmarTrocaEmailView.as_view(), name='confirmar_troca_email'),
    path('perfil/conta', views.ContaView.as_view(), name='excluir_conta'),
    path('perfil/conta/codigo', views.CodigoExclusaoView.as_view(), name='codigo_exclusao_conta'),
    path('perfil/exportacao', views.ExportacaoView.as_view(), name='exportacao_dados'),
    path('logout', views.LogoutView.as_view(), name='logout'),
]
