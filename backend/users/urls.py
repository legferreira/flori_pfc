# path: função do Django para declarar uma rota (URL -> view).
from django.urls import path
# Importa o módulo views.py inteiro (mesma pasta 'users'), para poder
# referenciar views.CadastroUsuarioView abaixo.
from . import views

# Lista de rotas deste app 'users'. É incluída (include) dentro de
# flori_backend/urls.py sob o prefixo 'api/', então a URL final fica
# 'api/usuarios'.
urlpatterns = [
    # 'usuarios' -> CadastroUsuarioView
    # .as_view() converte a classe baseada em View (definida em views.py) numa
    # função compatível com o roteador do Django; é isso que instancia a view
    # a cada requisição recebida.
    # name='cadastrar_usuario' -> apelido interno da rota, usado se precisarmos
    # gerar essa URL em outro lugar do código (ex: {% url 'cadastrar_usuario' %}).
    path('usuarios', views.CadastroUsuarioView.as_view(), name='cadastrar_usuario'),

]