"""
WSGI config for flori_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Define qual módulo de configurações usar (backend/flori_backend/settings.py)
# caso a variável de ambiente DJANGO_SETTINGS_MODULE ainda não esteja definida.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flori_backend.settings')

# Instancia o objeto 'application': é o ponto de entrada que um servidor WSGI
# (ex: gunicorn) chama para processar cada requisição HTTP em produção.
application = get_wsgi_application()
