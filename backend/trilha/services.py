import random
import secrets
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.utils import timezone

from .models import (
    QUIZ_PERCENTUAL_APROVACAO, QUIZ_PERGUNTAS_POR_TENTATIVA, Assunto, Card, Certificado, Fonte, GuiaRapido, Opcao,
    Pergunta, ProgressoCard, ProgressoTrilha, TentativaPergunta, TentativaQuiz, Trilha,
)

ALFABETO_CODIGO = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
MENSAGEM_QUIZ_EM_ATUALIZACAO = 'Quiz em atualização'
MENSAGEM_QUIZ_BLOQUEADO = 'Conclua todos os cards da trilha para liberar o quiz.'

sorteio = random.SystemRandom()


class ErroTrilha(Exception):
    def __init__(self, mensagem, status=400, campos=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status
        self.campos = campos


def percentual(parte, total):
    return round(parte / total * 100) if total else 0


def aprovado(acertos, total):
    return total > 0 and acertos * 100 >= QUIZ_PERCENTUAL_APROVACAO * total


def trilha_ativa():
    trilha = Trilha.objects.filter(ativa=True).first()
    if trilha is None:
        raise ErroTrilha('Nenhuma trilha disponível no momento.', status=404)
    return trilha


def cards_visiveis(trilha):
    return Card.objects.visiveis().oficiais().filter(assunto__trilha=trilha)


def perguntas_visiveis(trilha):
    return Pergunta.objects.visiveis().filter(trilha=trilha)


def opcoes_ativas(caminho='opcoes'):
    return Prefetch(caminho, queryset=Opcao.objects.filter(ativo=True))


def assuntos_visiveis(trilha, tipo=Assunto.Tipo.OFICIAL):
    cards = Card.objects.visiveis().prefetch_related('fontes')
    assuntos = (
        Assunto.objects.visiveis().filter(trilha=trilha, tipo=tipo)
        .prefetch_related(Prefetch('cards', queryset=cards)).order_by('ordem')
    )
    return [a for a in assuntos if a.cards.all()]


def guias_visiveis():
    fontes = Prefetch('fontes', queryset=Fonte.objects.filter(ativo=True))
    return list(GuiaRapido.objects.visiveis().prefetch_related(fontes).order_by('ordem'))


def conclusoes_da_usuaria(usuario, trilha):
    progresso = ProgressoCard.objects.filter(usuario=usuario, card__in=cards_visiveis(trilha))
    return {p.card_id: p.concluido_em for p in progresso}


def conclusao_da_trilha(usuario, trilha):
    registro = ProgressoTrilha.objects.filter(usuario=usuario, trilha=trilha).first()
    if registro and registro.trilha_concluida_em:
        return registro.trilha_concluida_em
    visiveis = cards_visiveis(trilha)
    total = visiveis.count()
    if total == 0 or ProgressoCard.objects.filter(usuario=usuario, card__in=visiveis).count() < total:
        return None
    try:
        with transaction.atomic():
            ProgressoTrilha.objects.get_or_create(usuario=usuario, trilha=trilha)
    except IntegrityError:
        pass
    ProgressoTrilha.objects.filter(usuario=usuario, trilha=trilha, trilha_concluida_em__isnull=True).update(
        trilha_concluida_em=timezone.now(),
    )
    return ProgressoTrilha.objects.get(usuario=usuario, trilha=trilha).trilha_concluida_em


def tentativas_finalizadas(usuario, trilha):
    return TentativaQuiz.objects.filter(usuario=usuario, trilha=trilha, finalizada_em__isnull=False)


def estado_do_quiz(trilha, liberado, usuario=None):
    ativas = perguntas_visiveis(trilha).count()
    estado = {
        'liberado': liberado,
        'disponivel': ativas > 0,
        'mensagem': None if ativas else MENSAGEM_QUIZ_EM_ATUALIZACAO,
        'total_perguntas': min(QUIZ_PERGUNTAS_POR_TENTATIVA, ativas),
        'nota_minima_percentual': QUIZ_PERCENTUAL_APROVACAO,
        'tentativas': 0,
        'em_andamento': False,
        'ultimo_acertos': None,
        'ultimo_total': None,
    }
    if usuario is None:
        return estado
    finalizadas = tentativas_finalizadas(usuario, trilha).order_by('-finalizada_em')
    ultima = finalizadas.first()
    estado.update({
        'tentativas': finalizadas.count(),
        'em_andamento': TentativaQuiz.objects.filter(usuario=usuario, trilha=trilha, finalizada_em__isnull=True).exists(),
        'ultimo_acertos': ultima.acertos if ultima else None,
        'ultimo_total': ultima.total_perguntas if ultima else None,
    })
    return estado


class ConsultarTrilha:
    def __init__(self, usuario):
        self.usuario = usuario

    def executar(self):
        trilha = trilha_ativa()
        assuntos = assuntos_visiveis(trilha)
        leitura = self.usuario.is_admin
        conclusoes = {} if leitura else conclusoes_da_usuaria(self.usuario, trilha)
        concluida_em = None if leitura else conclusao_da_trilha(self.usuario, trilha)
        certificado = None
        if not leitura:
            certificado = Certificado.objects.filter(usuario=self.usuario, trilha=trilha).select_related('tentativa').first()
        return {
            'trilha': trilha,
            'assuntos': assuntos,
            'conclusoes': conclusoes,
            'total_cards': sum(len(a.cards.all()) for a in assuntos),
            'concluidos': len(conclusoes),
            'trilha_concluida_em': concluida_em,
            'guias_rapidos': guias_visiveis(),
            'quiz': estado_do_quiz(trilha, leitura or concluida_em is not None, None if leitura else self.usuario),
            'certificado': certificado,
            'modo_visualizacao': leitura,
        }


class ConcluirCard:
    def __init__(self, usuario, card_id):
        self.usuario = usuario
        self.card_id = card_id

    def executar(self):
        card = Card.objects.visiveis().filter(pk=self.card_id).select_related('assunto__trilha').first()
        if card is None:
            raise ErroTrilha('Card não encontrado.', status=404)
        if card.assunto.extra:
            raise ErroTrilha('Conteúdos de "Para ir além" não registram progresso.', status=400)
        try:
            with transaction.atomic():
                progresso, _ = ProgressoCard.objects.get_or_create(usuario=self.usuario, card=card)
        except IntegrityError:
            progresso = ProgressoCard.objects.get(usuario=self.usuario, card=card)
        conclusao_da_trilha(self.usuario, card.assunto.trilha)
        return progresso


def perguntas_da_tentativa(tentativa):
    return list(
        tentativa.perguntas.select_related('pergunta__assunto')
        .prefetch_related(opcoes_ativas('pergunta__opcoes'))
        .order_by('ordem')
    )


class IniciarQuiz:
    def __init__(self, usuario):
        self.usuario = usuario

    def executar(self):
        trilha = trilha_ativa()
        if conclusao_da_trilha(self.usuario, trilha) is None:
            raise ErroTrilha(MENSAGEM_QUIZ_BLOQUEADO, status=403)
        with transaction.atomic():
            type(self.usuario).objects.select_for_update().filter(pk=self.usuario.pk).first()
            tentativa = self._em_andamento(trilha)
            if tentativa is None:
                tentativa = self._sortear(trilha)
        return trilha, tentativa, perguntas_da_tentativa(tentativa)

    def _em_andamento(self, trilha):
        return (
            TentativaQuiz.objects.filter(usuario=self.usuario, trilha=trilha, finalizada_em__isnull=True)
            .order_by('-criado_em').first()
        )

    def _sortear(self, trilha):
        ativas = list(perguntas_visiveis(trilha).values_list('id', flat=True))
        if not ativas:
            raise ErroTrilha(MENSAGEM_QUIZ_EM_ATUALIZACAO, status=409)
        quantidade = min(QUIZ_PERGUNTAS_POR_TENTATIVA, len(ativas))
        ultima = tentativas_finalizadas(self.usuario, trilha).order_by('-finalizada_em').first()
        repetidas = set(ultima.perguntas.values_list('pergunta_id', flat=True)) if ultima else set()
        novas = [p for p in ativas if p not in repetidas]
        if len(novas) >= quantidade:
            escolhidas = sorteio.sample(novas, quantidade)
        else:
            antigas = [p for p in ativas if p in repetidas]
            escolhidas = novas + sorteio.sample(antigas, quantidade - len(novas))
            sorteio.shuffle(escolhidas)
        tentativa = TentativaQuiz.objects.create(usuario=self.usuario, trilha=trilha, total_perguntas=quantidade)
        TentativaPergunta.objects.bulk_create(
            TentativaPergunta(tentativa=tentativa, pergunta_id=pergunta_id, ordem=ordem)
            for ordem, pergunta_id in enumerate(escolhidas, start=1)
        )
        return tentativa


class ConsultarQuiz:
    def __init__(self, usuario):
        self.usuario = usuario

    def executar(self):
        trilha = trilha_ativa()
        if self.usuario.is_admin:
            perguntas = list(perguntas_visiveis(trilha).prefetch_related(opcoes_ativas()).order_by('ordem'))
            if not perguntas:
                raise ErroTrilha(MENSAGEM_QUIZ_EM_ATUALIZACAO, status=409)
            return trilha, None, perguntas
        if conclusao_da_trilha(self.usuario, trilha) is None:
            raise ErroTrilha(MENSAGEM_QUIZ_BLOQUEADO, status=403)
        tentativa = (
            TentativaQuiz.objects.filter(usuario=self.usuario, trilha=trilha, finalizada_em__isnull=True)
            .order_by('-criado_em').first()
        )
        if tentativa is None:
            raise ErroTrilha('Nenhuma tentativa em andamento.', status=404)
        return trilha, tentativa, [item.pergunta for item in perguntas_da_tentativa(tentativa)]


class EnviarQuiz:
    def __init__(self, usuario, dados):
        self.usuario = usuario
        self._respostas = dados.get('respostas')
        self._tentativa_id = dados.get('tentativa_id')

    def executar(self):
        trilha = trilha_ativa()
        if not isinstance(self._respostas, dict):
            raise ErroTrilha('Envie as respostas do quiz.')
        with transaction.atomic():
            tentativa = self._tentativa(trilha)
            itens = perguntas_da_tentativa(tentativa)
            escolhas = self._validar(itens)
            acertos = 0
            assuntos = {}
            for item in itens:
                item.opcao_escolhida = escolhas[item.pk]
                item.acertou = item.opcao_escolhida.correta
                if item.acertou:
                    acertos += 1
                elif item.pergunta.assunto is not None:
                    assuntos[item.pergunta.assunto_id] = item.pergunta.assunto
            TentativaPergunta.objects.bulk_update(itens, ['opcao_escolhida', 'acertou'])
            tentativa.acertos = acertos
            tentativa.percentual = percentual(acertos, tentativa.total_perguntas)
            tentativa.aprovada = aprovado(acertos, tentativa.total_perguntas)
            tentativa.finalizada_em = timezone.now()
            tentativa.save(update_fields=['acertos', 'percentual', 'aprovada', 'finalizada_em'])
            certificado = self._emitir_certificado(trilha, tentativa) if tentativa.aprovada else None

        return {
            'tentativa': tentativa,
            'trilha': trilha,
            'assuntos_a_revisar': [] if tentativa.aprovada else sorted(assuntos.values(), key=lambda a: a.ordem),
            'certificado': certificado or Certificado.objects.filter(usuario=self.usuario, trilha=trilha).first(),
        }

    def _tentativa(self, trilha):
        try:
            tentativa_id = uuid.UUID(str(self._tentativa_id))
        except ValueError:
            raise ErroTrilha('Tentativa não encontrada.', status=404)
        tentativa = (
            TentativaQuiz.objects.select_for_update()
            .filter(pk=tentativa_id, usuario=self.usuario, trilha=trilha).first()
        )
        if tentativa is None:
            raise ErroTrilha('Tentativa não encontrada.', status=404)
        if tentativa.finalizada:
            raise ErroTrilha('Esta tentativa já foi enviada. Comece uma nova.', status=409)
        return tentativa

    def _validar(self, itens):
        escolhas = {}
        for item in itens:
            opcao_id = self._respostas.get(str(item.pergunta_id))
            if not opcao_id:
                raise ErroTrilha('Responda todas as perguntas antes de enviar.')
            opcao = next((o for o in item.pergunta.opcoes.all() if str(o.id) == str(opcao_id)), None)
            if opcao is None:
                raise ErroTrilha('Uma das respostas não pertence à pergunta.')
            escolhas[item.pk] = opcao
        return escolhas

    def _emitir_certificado(self, trilha, tentativa):
        if Certificado.objects.filter(usuario=self.usuario, trilha=trilha).exists():
            return None
        try:
            with transaction.atomic():
                return Certificado.objects.create(
                    usuario=self.usuario, trilha=trilha, tentativa=tentativa,
                    codigo=self._novo_codigo(),
                    nome_completo=f'{self.usuario.nome} {self.usuario.sobrenome}',
                )
        except IntegrityError:
            return None

    def _novo_codigo(self):
        while True:
            letras = ''.join(secrets.choice(ALFABETO_CODIGO) for _ in range(8))
            codigo = f'FLORI-{letras[:4]}-{letras[4:]}'
            if not Certificado.objects.filter(codigo=codigo).exists():
                return codigo


class ConsultarExtras:
    def executar(self):
        trilha = trilha_ativa()
        return assuntos_visiveis(trilha, tipo=Assunto.Tipo.EXTRA)


class ConsultarCertificado:
    def __init__(self, usuario):
        self.usuario = usuario

    def executar(self):
        trilha = trilha_ativa()
        certificado = (
            Certificado.objects.filter(usuario=self.usuario, trilha=trilha)
            .select_related('tentativa').first()
        )
        if certificado is None:
            raise ErroTrilha('Você ainda não tem certificado. Conclua o quiz com a nota mínima.', status=404)
        return trilha, certificado


class ConsultarDashboard:
    def __init__(self, usuario):
        self.usuario = usuario

    def executar(self):
        trilha = trilha_ativa()
        conclusoes = conclusoes_da_usuaria(self.usuario, trilha)
        conclusao_da_trilha(self.usuario, trilha)
        assuntos = []
        for assunto in assuntos_visiveis(trilha):
            cards = list(assunto.cards.all())
            feitos = sum(1 for c in cards if c.id in conclusoes)
            assuntos.append({
                'id': assunto.id, 'titulo': assunto.titulo, 'cor': assunto.cor,
                'concluidos': feitos, 'total': len(cards), 'percentual': percentual(feitos, len(cards)),
            })
        total = sum(a['total'] for a in assuntos)
        tentativas = tentativas_finalizadas(self.usuario, trilha)
        melhor = tentativas.order_by('-percentual').first()
        return {
            'concluidos': len(conclusoes),
            'total': total,
            'percentual': percentual(len(conclusoes), total),
            'tentativas': tentativas.count(),
            'melhor_nota_percentual': melhor.percentual if melhor else None,
            'assuntos': assuntos,
        }
