# admin: módulo do Django que permite registrar models para que apareçam
#        e sejam editáveis pela interface administrativa web (/admin/).
from django.contrib import admin

# Register your models here.
# Nenhum model (Usuario, Consentimento) foi registrado ainda com admin.register().
# Enquanto isso não for feito, os dados dessas tabelas não aparecem no painel
# /admin/ do Django — só são acessíveis via código (services.py) ou banco direto.
# Exemplo de como registrar, se for necessário no futuro:
#   from .models import Usuario, Consentimento
#   admin.site.register(Usuario)
#   admin.site.register(Consentimento)
