from django.core.management.base import BaseCommand
from django.db import transaction

from users.management.commands.popular_demo import DOMINIO_DEMO, exigir_debug
from users.models import Consentimento, LogAtividade, Usuario
from users.services import ExcluirConta


class Command(BaseCommand):
    help = (
        'Exclui os users de demonstração criados pelo popular_demo com o serviço ExcluirConta. '
        'Com --definitivo, também apaga as linhas desses users do banco (os logs ficam, sem vínculo).'
    )

    def add_arguments(self, parser):
        parser.add_argument('--forcar', action='store_true')
        parser.add_argument('--definitivo', action='store_true')

    def handle(self, *args, **options):
        exigir_debug(options)
        demos = Usuario.objects.filter(demo=True, perfil=Usuario.Perfil.USER)
        ativos = list(demos.ativos().filter(email__endswith=DOMINIO_DEMO).values_list('id', flat=True))
        for usuario_id in ativos:
            ExcluirConta(usuario_id, acao=LogAtividade.Acao.EXCLUSAO_CONTA_DEMO).executar()
        self.stdout.write(self.style.SUCCESS(f'{len(ativos)} users de demonstração excluídos.'))

        if options['definitivo']:
            with transaction.atomic():
                Consentimento.objects.filter(usuario__in=demos).delete()
                apagados = demos.apagar_demo_definitivo()[1].get('users.Usuario', 0)
            self.stdout.write(self.style.SUCCESS(f'{apagados} linhas de demonstração apagadas do banco.'))
