from django.core.management.base import BaseCommand
from django.db import transaction

from trilha import conteudo
from trilha.models import Assunto, Card, Fonte, FonteCard, GuiaRapido, Opcao, Pergunta, Trilha


def proxima_ordem(consulta):
    ultima = consulta.nao_excluidos().order_by('-ordem').values_list('ordem', flat=True).first()
    return (ultima or 0) + 1


class Command(BaseCommand):
    help = (
        'Cria no banco o conteúdo de trilha/conteudo.py que ainda não existe, identificando cada item pelo código. '
        'Nunca altera o que já existe, nunca restaura o que foi excluído e nunca muda a ordem.'
    )

    @transaction.atomic
    def handle(self, *args, **options):
        self.criados = {'assuntos': 0, 'cards': 0, 'guias': 0, 'perguntas': 0}
        trilha, criada = Trilha.objects.get_or_create(
            nome=conteudo.NOME_TRILHA,
            defaults={
                'carga_horaria_minutos': conteudo.CARGA_HORARIA_MINUTOS,
                'nota_minima_percentual': conteudo.NOTA_MINIMA_PERCENTUAL,
            },
        )
        assuntos = {dados['ordem']: self._assunto(trilha, dados) for dados in conteudo.ASSUNTOS}
        self._guia()
        self._perguntas(trilha, assuntos)

        if not criada and not any(self.criados.values()):
            self.stdout.write(self.style.WARNING(
                'A trilha já está no banco. Nada foi alterado: edite o conteúdo pela área admin.'
            ))
            return
        resumo = ', '.join(f'{n} {nome}' for nome, n in self.criados.items())
        self.stdout.write(self.style.SUCCESS(f'Trilha carregada: {resumo} criados.'))

    def _assunto(self, trilha, dados):
        codigo = f"A{dados['ordem']}"
        assunto = Assunto.objects.filter(codigo=codigo).first()
        if assunto is None:
            assunto = Assunto.objects.create(
                trilha=trilha, codigo=codigo, titulo=dados['titulo'], descricao=dados['descricao'], cor=dados['cor'],
                ordem=proxima_ordem(Assunto.objects.filter(trilha=trilha).oficiais()),
            )
            self.criados['assuntos'] += 1
        for c in dados['cards']:
            if Card.objects.filter(codigo=c['codigo']).exists():
                continue
            card = Card.objects.create(
                assunto=assunto, codigo=c['codigo'], tema=c['tema'], explicacao=c['explicacao'],
                exemplo=c['exemplo'], secoes=c['secoes'], cta=c['cta'],
                ordem=proxima_ordem(Card.objects.filter(assunto=assunto)),
            )
            FonteCard.objects.bulk_create(
                FonteCard(card=card, nome=conteudo.FONTES[chave]['nome'], url=conteudo.FONTES[chave]['url'], ordem=i)
                for i, chave in enumerate(c['fontes'], start=1)
            )
            self.criados['cards'] += 1
        return assunto

    def _guia(self):
        dados = conteudo.GUIA_RAPIDO
        if GuiaRapido.objects.filter(codigo=dados['codigo']).exists():
            return
        guia = GuiaRapido.objects.create(
            codigo=dados['codigo'], titulo=dados['titulo'], introducao=dados['introducao'],
            passos=list(dados['passos']), ordem=proxima_ordem(GuiaRapido.objects.all()),
        )
        fontes = []
        for chave in dados['fontes']:
            fonte, _ = Fonte.objects.get_or_create(
                url=conteudo.FONTES[chave]['url'], defaults={'nome': conteudo.FONTES[chave]['nome']},
            )
            fontes.append(fonte)
        guia.fontes.set(fontes)
        self.criados['guias'] += 1

    def _perguntas(self, trilha, assuntos):
        for dados in conteudo.PERGUNTAS:
            if Pergunta.objects.filter(codigo=dados['codigo']).exists():
                continue
            pergunta = Pergunta.objects.create(
                trilha=trilha, assunto=assuntos.get(dados['assunto']), codigo=dados['codigo'],
                enunciado=dados['enunciado'], ordem=proxima_ordem(Pergunta.objects.filter(trilha=trilha)),
            )
            Opcao.objects.bulk_create(
                Opcao(pergunta=pergunta, texto=texto, correta=(i == dados['correta']), ordem=i + 1)
                for i, texto in enumerate(dados['opcoes'])
            )
            self.criados['perguntas'] += 1
