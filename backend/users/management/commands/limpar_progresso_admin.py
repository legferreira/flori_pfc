from django.core.management.base import BaseCommand
from django.db import transaction

from trilha.models import Certificado, ProgressoCard, ProgressoTrilha, TentativaQuiz
from users.auditoria import registrar_log
from users.models import LogAtividade, Usuario


class Command(BaseCommand):
    help = 'Apaga progresso na trilha, tentativas do quiz e certificados de contas com perfil admin.'

    def handle(self, *args, **options):
        admins = Usuario.objects.filter(perfil=Usuario.Perfil.ADMIN)
        with transaction.atomic():
            certificados = Certificado.objects.filter(usuario__in=admins)
            contas = set(certificados.values_list('usuario_id', flat=True))
            tentativas = TentativaQuiz.objects.filter(usuario__in=admins)
            contas |= set(tentativas.values_list('usuario_id', flat=True))
            progresso = ProgressoCard.objects.filter(usuario__in=admins)
            contas |= set(progresso.values_list('usuario_id', flat=True))
            conclusoes = ProgressoTrilha.objects.filter(usuario__in=admins)
            contas |= set(conclusoes.values_list('usuario_id', flat=True))
            apagados = {
                'certificados': certificados.delete()[0],
                'tentativas_quiz': tentativas.count(),
                'progresso_cards': progresso.delete()[0],
            }
            tentativas.delete()
            conclusoes.delete()
            if contas:
                registrar_log(
                    None, LogAtividade.Acao.PROGRESSO_ADMIN_LIMPO, alvo_tipo='usuario',
                    resumo={'contas_admin': len(contas), **apagados},
                )

        if not contas:
            self.stdout.write('Nenhum registro de trilha em contas admin, nada foi apagado.')
            return
        self.stdout.write(self.style.SUCCESS(
            f'{len(contas)} contas admin limpas: {apagados["progresso_cards"]} cards concluídos, '
            f'{apagados["tentativas_quiz"]} tentativas do quiz e {apagados["certificados"]} certificados apagados.'
        ))
