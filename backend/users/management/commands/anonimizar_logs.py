from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from users.models import (
    CodigoAutenticacao, Consentimento, LogAtividade, SolicitacaoRedefinicaoSenha, TentativaLogin, TrocaEmailPendente,
)
from users.services import LoginUsuario, SolicitarRedefinicaoSenha


class Command(BaseCommand):
    help = (
        'Remove o IP dos logs e dos consentimentos vencidos (as linhas ficam para sempre) e apaga registros '
        'temporários expirados que não são log.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        agora = timezone.now()

        def dias(n):
            return agora - timedelta(days=n)

        com_ip = LogAtividade.objects.filter(ip_origem__isnull=False)
        resultados = {
            'logs comuns sem IP': com_ip.comuns()
            .filter(criado_em__lt=dias(settings.LOG_RETENCAO_DIAS)).anonimizar_ip(),
            'logs administrativos sem IP': com_ip.administrativos()
            .filter(criado_em__lt=dias(settings.LOG_RETENCAO_ADMIN_DIAS)).anonimizar_ip(),
            'consentimentos sem IP': Consentimento.objects.filter(
                ip_origem__isnull=False, data_consentimento__lt=dias(settings.CONSENTIMENTO_RETENCAO_DIAS),
            ).update(ip_origem=None),
            'códigos 2FA expirados': CodigoAutenticacao.objects.filter(expira_em__lt=agora).delete()[0],
            'pedidos de redefinição expirados': SolicitacaoRedefinicaoSenha.objects.filter(
                criado_em__lt=agora - SolicitarRedefinicaoSenha.JANELA_CONTAGEM,
            ).delete()[0],
            'trocas de email expiradas': TrocaEmailPendente.objects.filter(expira_em__lt=agora).delete()[0],
            'tentativas de login antigas': TentativaLogin.objects.filter(
                criado_em__lt=agora - LoginUsuario.JANELA_BLOQUEIO,
            ).delete()[0],
        }
        for nome, quantidade in resultados.items():
            self.stdout.write(f'{nome}: {quantidade}')
        self.stdout.write(self.style.SUCCESS('Concluído. Nenhum log foi apagado.'))
