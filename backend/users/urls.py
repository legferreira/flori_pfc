
from django.urls import path

from . import views
from .views import CadastroUsuarioView, LoginUsuarioView, PerfilView

urlpatterns = [
    path('usuarios', views.CadastroUsuarioView.as_view(), name='cadastrar_usuario'),
    # Cadastro pelo Google: e-mail vem do ID token do Firebase, conta sem senha.
    path('usuarios/google', views.CadastroGoogleView.as_view(), name='cadastrar_usuario_google'),
    path('login', views.LoginUsuarioView.as_view(), name='login_usuario'),
    # Segunda etapa do login (2FA): confere o código de 6 dígitos enviado por e-mail.
    path('login/verificar', views.VerificarCodigoView.as_view(), name='verificar_codigo'),
    # Login com Google (Firebase): recebe o ID token e devolve o token de sessão do Flori.
    path('login/google', views.LoginGoogleView.as_view(), name='login_google'),
    # "Esqueci a senha": envia por e-mail um token provisório de redefinição,
    # com espera crescente entre pedidos (2, 4, 8... minutos).
    path('resetar-senha', views.ResetarSenhaView.as_view(), name='resetar_senha'),
    # Segunda etapa: recebe o token do link do e-mail + a nova senha.
    path('resetar-senha/confirmar', views.ConfirmarResetarSenhaView.as_view(), name='confirmar_resetar_senha'),
    # Rota protegida: só responde com token válido no header Authorization
    path('perfil', views.PerfilView.as_view(), name='perfil'),
    # Sair: apaga o token de sessão enviado no header Authorization.
    path('logout', views.LogoutView.as_view(), name='logout'),
]