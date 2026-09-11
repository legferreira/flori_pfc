"""
ASGI config for flori_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# Mesma ideia do wsgi.py, mas para o padrão assíncrono (ASGI), usado por
# servidores como uvicorn/daphne (necessário para WebSockets/async views).
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flori_backend.settings')

# Objeto 'application' equivalente ao de wsgi.py, só que na interface ASGI.
application = get_asgi_application()
