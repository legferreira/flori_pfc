from django.core.management.base import BaseCommand
from django.db import transaction

from diario.constantes import SINTOMAS_INICIAIS
from diario.models import Sintoma


class Command(BaseCommand):
    help = 'Cria os sintomas iniciais do diário que ainda não existem, pelo código. Nunca altera o que já existe.'

    @transaction.atomic
    def handle(self, *args, **options):
        criados = 0
        for ordem, (codigo, nome) in enumerate(SINTOMAS_INICIAIS, start=1):
            _, criado = Sintoma.objects.get_or_create(codigo=codigo, defaults={'nome': nome, 'ordem': ordem})
            criados += criado
        if criados:
            self.stdout.write(self.style.SUCCESS(f'{criados} sintomas criados.'))
        else:
            self.stdout.write(self.style.WARNING('Os sintomas já estão no banco. Nada foi alterado.'))
