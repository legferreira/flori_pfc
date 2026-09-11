# admin: módulo padrão do Django que fornece a interface administrativa pronta
#        (tela web para gerenciar os models cadastrados em admin.py de cada app).
from django.contrib import admin
# path: declara uma rota individual. include: encaixa as rotas de outro
#       módulo urls.py dentro de um prefixo desta lista.
from django.urls import path, include

# Tabela de roteamento raiz do projeto (ROOT_URLCONF, definido em settings.py).
# Toda requisição HTTP que chega ao Django passa primeiro por esta lista.
urlpatterns = [
    # /admin/... -> painel administrativo automático do Django
    # (admin.site.urls é o conjunto de rotas geradas pelo Django admin).
    path('admin/', admin.site.urls),
    # /api/... -> delega para as rotas definidas em users/urls.py.
    # Por isso o endpoint de cadastro (path('usuarios', ...) em users/urls.py)
    # fica acessível em /api/usuarios.
    path('api/', include('users.urls')),
]
