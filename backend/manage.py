#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Aponta para backend/flori_backend/settings.py antes de qualquer comando rodar.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flori_backend.settings')
    try:
        # Import feito dentro do try para dar uma mensagem de erro amigável
        # caso o Django não esteja instalado/ativado no ambiente virtual.
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    # sys.argv -> lista de argumentos passados no terminal
    # (ex: ['manage.py', 'runserver'] ou ['manage.py', 'test']).
    # Essa função interpreta o comando e o executa.
    execute_from_command_line(sys.argv)


# Só roda main() se este arquivo for executado diretamente
# (python manage.py ...), não quando importado por outro módulo.
if __name__ == '__main__':
    main()
