from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from trilha import conteudo_extras
from trilha.models import Assunto, Card, FonteCard, Trilha


def proxima_ordem(consulta):
    ultima = consulta.nao_excluidos().order_by('-ordem').values_list('ordem', flat=True).first()
    return (ultima or 0) + 1


class Command(BaseCommand):
    help = (
        'Cria os assuntos extras de "Para ir além" que ainda não existem, identificando cada item pelo código. '
        'Tudo nasce desativado, como rascunho para validação, e nada que já existe é alterado.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        trilha = Trilha.objects.filter(ativa=True).first()
        if trilha is None:
            raise CommandError('Rode carregar_trilha antes de carregar os extras.')
        criados = {'assuntos': 0, 'cards': 0}
        for dados in conteudo_extras.ASSUNTOS:
            assunto = Assunto.objects.filter(codigo=dados['codigo']).first()
            if assunto is None:
                assunto = Assunto.objects.create(
                    trilha=trilha, tipo=Assunto.Tipo.EXTRA, codigo=dados['codigo'], titulo=dados['titulo'],
                    descricao=dados['descricao'], cor=dados['cor'], ativo=False,
                    ordem=proxima_ordem(Assunto.objects.filter(trilha=trilha).extras()),
                )
                criados['assuntos'] += 1
            for c in dados['cards']:
                if Card.objects.filter(codigo=c['codigo']).exists():
                    continue
                card = Card.objects.create(
                    assunto=assunto, codigo=c['codigo'], tema=c['titulo'], explicacao=c['explicacao'],
                    exemplo=c['exemplo'], ativo=False, ordem=proxima_ordem(Card.objects.filter(assunto=assunto)),
                )
                FonteCard.objects.bulk_create(
                    FonteCard(card=card, nome=f['nome'], url=f['url'], ordem=i)
                    for i, f in enumerate(conteudo_extras.FONTES, start=1)
                )
                criados['cards'] += 1

        if not any(criados.values()):
            self.stdout.write(self.style.WARNING('Os extras já estão no banco. Nada foi alterado.'))
            return
        self.stdout.write(self.style.SUCCESS(
            f'{criados["assuntos"]} assuntos e {criados["cards"]} cards extras criados, todos desativados. '
            'Ative pela área admin depois da validação do conteúdo.'
        ))
