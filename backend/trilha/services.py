import secrets

from django.db import IntegrityError, transaction
from django.db.models import Prefetch

from .models import Assunto, Card, Certificado, GuiaRapido, ProgressoCard, TentativaQuiz, Trilha

ALFABETO_CODIGO = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'


class ErroTrilha(Exception):
    def __init__(self, mensagem, status=400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status


def percentual(parte, total):
    return round(parte / total * 100) if total else 0


def trilha_ativa():
    trilha = Trilha.objects.filter(ativa=True).first()
    if trilha is None:
        raise ErroTrilha('Nenhuma trilha disponível no momento.', status=404)
    return trilha


def assuntos_da_trilha(trilha):
    cards = Card.objects.prefetch_related('fontes')
    return Assunto.objects.filter(trilha=trilha).prefetch_related(Prefetch('cards', queryset=cards))


def conclusoes_da_usuaria(usuario, trilha):
    progresso = ProgressoCard.objects.filter(usuario=usuario, card__assunto__trilha=trilha)
    return {p.card_id: p.concluido_em for p in progresso}


def trilha_concluida(usuario, trilha):
    total = Card.objects.filter(assunto__trilha=trilha).count()
    feitos = ProgressoCard.objects.filter(usuario=usuario, card__assunto__trilha=trilha).count()
    return total > 0 and feitos == total


class ConsultarTrilha:
    def __init__(self, usuario):
        self.usuario = usuario

    def executar(self):
        trilha = trilha_ativa()
        assuntos = list(assuntos_da_trilha(trilha))
        conclusoes = conclusoes_da_usuaria(self.usuario, trilha)
        total = sum(len(a.cards.all()) for a in assuntos)
        return {
            'trilha': trilha,
            'assuntos': assuntos,
            'conclusoes': conclusoes,
            'total_cards': total,
            'concluidos': len(conclusoes),
            'guia_rapido': GuiaRapido.objects.filter(ativo=True).prefetch_related('fontes').first(),
            'quiz': self._estado_do_quiz(trilha, total, len(conclusoes)),
            'certificado': Certificado.objects.filter(usuario=self.usuario, trilha=trilha).select_related('tentativa').first(),
        }

    def _estado_do_quiz(self, trilha, total_cards, concluidos):
        tentativas = TentativaQuiz.objects.filter(usuario=self.usuario, trilha=trilha).order_by('-criado_em')
        ultima = tentativas.first()
        return {
            'liberado': total_cards > 0 and concluidos == total_cards,
            'total_perguntas': trilha.perguntas.count(),
            'tentativas': tentativas.count(),
            'ultimo_acertos': ultima.acertos if ultima else None,
        }


class ConcluirCard:
    def __init__(self, usuario, card_id):
        self.usuario = usuario
        self.card_id = card_id

    def executar(self):
        card = Card.objects.filter(pk=self.card_id, assunto__trilha__ativa=True).select_related('assunto').first()
        if card is None:
            raise ErroTrilha('Card não encontrado.', status=404)

        try:
            progresso, _ = ProgressoCard.objects.get_or_create(usuario=self.usuario, card=card)
        except IntegrityError:
            progresso = ProgressoCard.objects.get(usuario=self.usuario, card=card)
        return progresso


class ConsultarQuiz:
    def __init__(self, usuario):
        self.usuario = usuario

    def executar(self):
        trilha = trilha_ativa()
        if not trilha_concluida(self.usuario, trilha):
            raise ErroTrilha('Conclua todos os cards da trilha para liberar o quiz.', status=403)
        perguntas = trilha.perguntas.prefetch_related('opcoes')
        return trilha, list(perguntas)


class EnviarQuiz:
    def __init__(self, usuario, dados):
        self.usuario = usuario
        self._respostas = dados.get('respostas')

    def executar(self):
        trilha = trilha_ativa()
        if not trilha_concluida(self.usuario, trilha):
            raise ErroTrilha('Conclua todos os cards da trilha para liberar o quiz.', status=403)

        perguntas = list(trilha.perguntas.select_related('assunto').prefetch_related('opcoes'))
        escolhas = self._validar_respostas(perguntas)

        acertos, assuntos_a_revisar = self._corrigir(perguntas, escolhas)
        total = len(perguntas)
        percentual_final = percentual(acertos, total)
        aprovada = percentual_final >= trilha.nota_minima_percentual

        with transaction.atomic():
            tentativa = TentativaQuiz.objects.create(
                usuario=self.usuario, trilha=trilha, acertos=acertos, total=total,
                percentual=percentual_final, aprovada=aprovada,
            )
            certificado = self._emitir_certificado(trilha, tentativa) if aprovada else None

        return {
            'tentativa': tentativa,
            'trilha': trilha,
            'assuntos_a_revisar': [] if aprovada else assuntos_a_revisar,
            'certificado': certificado or Certificado.objects.filter(usuario=self.usuario, trilha=trilha).first(),
        }

    def _validar_respostas(self, perguntas):
        if not isinstance(self._respostas, dict):
            raise ErroTrilha('Envie as respostas do quiz.')

        escolhas = {}
        for pergunta in perguntas:
            opcao_id = self._respostas.get(str(pergunta.id))
            opcao = next((o for o in pergunta.opcoes.all() if str(o.id) == opcao_id), None)
            if opcao is None:
                raise ErroTrilha('Responda todas as perguntas antes de enviar.')
            escolhas[pergunta.id] = opcao
        return escolhas

    def _corrigir(self, perguntas, escolhas):
        acertos = 0
        assuntos = {}
        for pergunta in perguntas:
            if escolhas[pergunta.id].correta:
                acertos += 1
            else:
                assuntos[pergunta.assunto_id] = pergunta.assunto
        return acertos, sorted(assuntos.values(), key=lambda a: a.ordem)

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
        assuntos = []
        for assunto in assuntos_da_trilha(trilha):
            cards = list(assunto.cards.all())
            feitos = sum(1 for c in cards if c.id in conclusoes)
            assuntos.append({
                'id': assunto.id, 'titulo': assunto.titulo, 'cor': assunto.cor,
                'concluidos': feitos, 'total': len(cards), 'percentual': percentual(feitos, len(cards)),
            })
        total = sum(a['total'] for a in assuntos)
        tentativas = TentativaQuiz.objects.filter(usuario=self.usuario, trilha=trilha)
        melhor = tentativas.order_by('-percentual').first()
        return {
            'concluidos': len(conclusoes),
            'total': total,
            'percentual': percentual(len(conclusoes), total),
            'tentativas': tentativas.count(),
            'melhor_nota_percentual': melhor.percentual if melhor else None,
            'assuntos': assuntos,
        }
