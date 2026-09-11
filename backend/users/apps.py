# AppConfig: classe base do Django para configurar metadados de um app
#            (cada app Django precisa de uma subclasse dessas).
from django.apps import AppConfig


# Declaração da classe de configuração do app 'users'.
# É referenciada indiretamente por INSTALLED_APPS em settings.py (via string 'users';
# o Django encontra esta classe automaticamente dentro do pacote).
class UsersConfig(AppConfig):
    # Nome do app, tem que bater com o nome da pasta/pacote Python ('users').
    # É esse nome que aparece em INSTALLED_APPS e é usado em migrations, db_table, etc.
    name = 'users'
