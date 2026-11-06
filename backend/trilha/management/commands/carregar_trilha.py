from django.core.management.base import BaseCommand
from django.db import transaction

from trilha import conteudo
from trilha.models import Assunto, Card, Fonte, GuiaRapido, Opcao, Pergunta, Trilha


class Command(BaseCommand):
    help = 'Grava o conteúdo de trilha/conteudo.py no banco. Pode rodar de novo: atualiza sem duplicar.'

    @transaction.atomic
    def handle(self, *args, **options):
        fontes = {chave: self._fonte(dados) for chave, dados in conteudo.FONTES.items()}
        trilha = self._trilha()
        assuntos = {a['ordem']: self._assunto(trilha, a, fontes) for a in conteudo.ASSUNTOS}
        self._guia(fontes)
        self._perguntas(trilha, assuntos)
        self.stdout.write(self.style.SUCCESS(
            f'Trilha carregada: {Card.objects.count()} cards, {Pergunta.objects.count()} perguntas.'
        ))

    def _fonte(self, dados):
        fonte, _ = Fonte.objects.update_or_create(url=dados['url'], defaults={'nome': dados['nome']})
        return fonte

    def _trilha(self):
        trilha, _ = Trilha.objects.update_or_create(
            nome=conteudo.NOME_TRILHA,
            defaults={
                'carga_horaria_minutos': conteudo.CARGA_HORARIA_MINUTOS,
                'nota_minima_percentual': conteudo.NOTA_MINIMA_PERCENTUAL,
            },
        )
        return trilha

    def _assunto(self, trilha, dados, fontes):
        assunto, _ = Assunto.objects.update_or_create(
            trilha=trilha, ordem=dados['ordem'],
            defaults={'titulo': dados['titulo'], 'descricao': dados['descricao'], 'cor': dados['cor']},
        )
        for c in dados['cards']:
            card, _ = Card.objects.update_or_create(
                codigo=c['codigo'],
                defaults={
                    'assunto': assunto, 'ordem': c['ordem'], 'tema': c['tema'], 'explicacao': c['explicacao'],
                    'exemplo': c['exemplo'], 'secoes': c['secoes'], 'cta': c['cta'],
                },
            )
            card.fontes.set([fontes[chave] for chave in c['fontes']])
        return assunto

    def _guia(self, fontes):
        dados = conteudo.GUIA_RAPIDO
        guia, _ = GuiaRapido.objects.update_or_create(
            titulo=dados['titulo'],
            defaults={'introducao': dados['introducao'], 'passos': dados['passos']},
        )
        guia.fontes.set([fontes[chave] for chave in dados['fontes']])

    def _perguntas(self, trilha, assuntos):
        for ordem, dados in enumerate(conteudo.PERGUNTAS, start=1):
            pergunta, _ = Pergunta.objects.update_or_create(
                codigo=dados['codigo'],
                defaults={
                    'trilha': trilha, 'assunto': assuntos[dados['assunto']],
                    'enunciado': dados['enunciado'], 'ordem': ordem,
                },
            )
            pergunta.opcoes.all().delete()
            Opcao.objects.bulk_create(
                Opcao(pergunta=pergunta, texto=texto, correta=(i == dados['correta']), ordem=i + 1)
                for i, texto in enumerate(dados['opcoes'])
            )
