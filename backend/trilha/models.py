import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

QUIZ_PERGUNTAS_POR_TENTATIVA = 10
QUIZ_PERCENTUAL_APROVACAO = 70
AVISO_EXTRA = (
    'Este conteúdo é informativo e não faz diagnóstico. Se algo aqui parecer com o que você sente, converse com um '
    'responsável ou uma pessoa de confiança e procure um médico ou uma unidade de saúde. Em caso de dor muito forte, '
    'desmaio ou sangramento muito intenso com tontura, procure atendimento de urgência.'
)
MENSAGEM_PERGUNTA_EXTRA = 'Pergunta do quiz só pode ser ligada a um assunto da trilha oficial.'


class ConteudoQuerySet(models.QuerySet):
    filtros_do_pai = {}

    def nao_excluidos(self):
        return self.filter(excluido_em__isnull=True)

    def excluidos(self):
        return self.filter(excluido_em__isnull=False)

    def na_situacao(self, situacao):
        if situacao == 'excluidos':
            return self.excluidos()
        if situacao == 'todos':
            return self
        return self.nao_excluidos()

    def visiveis(self):
        return self.filter(ativo=True, excluido_em__isnull=True, **self.filtros_do_pai)


class AssuntoQuerySet(ConteudoQuerySet):
    filtros_do_pai = {'trilha__ativa': True}

    def oficiais(self):
        return self.filter(tipo=Assunto.Tipo.OFICIAL)

    def extras(self):
        return self.filter(tipo=Assunto.Tipo.EXTRA)


class CardQuerySet(ConteudoQuerySet):
    filtros_do_pai = {
        'assunto__ativo': True, 'assunto__excluido_em__isnull': True, 'assunto__trilha__ativa': True,
    }

    def oficiais(self):
        return self.filter(assunto__tipo=Assunto.Tipo.OFICIAL)

    def extras(self):
        return self.filter(assunto__tipo=Assunto.Tipo.EXTRA)


class PerguntaQuerySet(ConteudoQuerySet):
    filtros_do_pai = {'trilha__ativa': True}


class GuiaQuerySet(ConteudoQuerySet):
    pass


class ConteudoGerenciavel(models.Model):
    ativo = models.BooleanField(default=True)
    excluido_em = models.DateTimeField(null=True, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def excluido(self):
        return self.excluido_em is not None


class Fonte(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=200)
    url = models.URLField(max_length=255, unique=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'trilha_fontes'

    def __str__(self):
        return self.nome


class Trilha(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=120)
    carga_horaria_minutos = models.PositiveSmallIntegerField(default=60)
    nota_minima_percentual = models.PositiveSmallIntegerField(default=QUIZ_PERCENTUAL_APROVACAO)
    ativa = models.BooleanField(default=True)

    class Meta:
        db_table = 'trilhas'

    def __str__(self):
        return self.nome


class Assunto(ConteudoGerenciavel):
    class Tipo(models.TextChoices):
        OFICIAL = 'oficial', 'Trilha oficial'
        EXTRA = 'extra', 'Para ir além'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trilha = models.ForeignKey(Trilha, on_delete=models.CASCADE, related_name='assuntos')
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.OFICIAL)
    codigo = models.CharField(max_length=20, unique=True, null=True, blank=True)
    titulo = models.CharField(max_length=100)
    descricao = models.CharField(max_length=200, blank=True)
    cor = models.CharField(max_length=7, help_text='Cor da marca em hexadecimal, ex: #EDBFD8')
    ordem = models.PositiveSmallIntegerField()

    objects = AssuntoQuerySet.as_manager()

    class Meta:
        db_table = 'trilha_assuntos'
        ordering = ['ordem']

    def __str__(self):
        return self.titulo

    @property
    def extra(self):
        return self.tipo == self.Tipo.EXTRA


class Card(ConteudoGerenciavel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assunto = models.ForeignKey(Assunto, on_delete=models.CASCADE, related_name='cards')
    codigo = models.CharField(max_length=10, unique=True)
    tema = models.CharField(max_length=100)
    explicacao = models.TextField()
    exemplo = models.CharField(max_length=255, blank=True)
    secoes = models.JSONField(default=list, blank=True)
    cta = models.CharField(max_length=255, blank=True)
    ordem = models.PositiveSmallIntegerField()

    objects = CardQuerySet.as_manager()

    class Meta:
        db_table = 'trilha_cards'
        ordering = ['ordem']

    def __str__(self):
        return f'{self.codigo} {self.tema}'


class FonteCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='fontes')
    nome = models.CharField(max_length=120)
    url = models.URLField(max_length=300)
    ordem = models.PositiveSmallIntegerField()

    class Meta:
        db_table = 'trilha_fontes_card'
        ordering = ['ordem']

    def __str__(self):
        return self.nome


class ProgressoCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey('users.Usuario', on_delete=models.CASCADE, related_name='progresso_trilha')
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='progressos')
    concluido_em = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'trilha_progresso'
        constraints = [models.UniqueConstraint(fields=['usuario', 'card'], name='progresso_unico_por_usuaria_e_card')]

    def __str__(self):
        return f'{self.usuario.apelido} concluiu {self.card.codigo}'


class ProgressoTrilha(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey('users.Usuario', on_delete=models.CASCADE, related_name='conclusoes_trilha')
    trilha = models.ForeignKey(Trilha, on_delete=models.CASCADE, related_name='conclusoes')
    trilha_concluida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'trilha_progresso_trilha'
        constraints = [models.UniqueConstraint(fields=['usuario', 'trilha'], name='progresso_trilha_unico_por_usuaria')]

    def __str__(self):
        return f'{self.usuario.apelido}: {self.trilha_concluida_em}'


class GuiaRapido(ConteudoGerenciavel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=10, unique=True, null=True, blank=True)
    titulo = models.CharField(max_length=100)
    introducao = models.CharField(max_length=255, blank=True)
    passos = models.JSONField(default=list)
    fontes = models.ManyToManyField(Fonte, related_name='guias_rapidos', blank=True)
    ordem = models.PositiveSmallIntegerField(default=1)

    objects = GuiaQuerySet.as_manager()

    class Meta:
        db_table = 'trilha_guias_rapidos'
        ordering = ['ordem']

    def __str__(self):
        return self.titulo


class Pergunta(ConteudoGerenciavel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trilha = models.ForeignKey(Trilha, on_delete=models.CASCADE, related_name='perguntas')
    assunto = models.ForeignKey(Assunto, on_delete=models.PROTECT, related_name='perguntas', null=True, blank=True)
    codigo = models.CharField(max_length=10, unique=True)
    enunciado = models.CharField(max_length=255)
    ordem = models.PositiveSmallIntegerField()

    objects = PerguntaQuerySet.as_manager()

    class Meta:
        db_table = 'trilha_perguntas'
        ordering = ['ordem']

    def __str__(self):
        return self.enunciado

    def clean(self):
        if self.assunto_id and Assunto.objects.filter(pk=self.assunto_id, tipo=Assunto.Tipo.EXTRA).exists():
            raise ValidationError({'assunto': MENSAGEM_PERGUNTA_EXTRA})


class Opcao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pergunta = models.ForeignKey(Pergunta, on_delete=models.CASCADE, related_name='opcoes')
    texto = models.CharField(max_length=200)
    correta = models.BooleanField(default=False)
    ordem = models.PositiveSmallIntegerField()
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'trilha_opcoes'
        ordering = ['ordem']
        constraints = [models.UniqueConstraint(fields=['pergunta', 'ordem'], name='opcao_ordem_unica_por_pergunta')]

    def __str__(self):
        return self.texto


class TentativaQuiz(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey('users.Usuario', on_delete=models.CASCADE, related_name='tentativas_quiz')
    trilha = models.ForeignKey(Trilha, on_delete=models.CASCADE, related_name='tentativas')
    total_perguntas = models.PositiveSmallIntegerField()
    acertos = models.PositiveSmallIntegerField(null=True, blank=True)
    percentual = models.PositiveSmallIntegerField(null=True, blank=True)
    aprovada = models.BooleanField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    finalizada_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'trilha_tentativas_quiz'
        indexes = [models.Index(fields=['usuario', 'trilha', '-criado_em'])]

    def __str__(self):
        return f'{self.usuario.apelido}: {self.acertos}/{self.total_perguntas}'

    @property
    def finalizada(self):
        return self.finalizada_em is not None


class TentativaPergunta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tentativa = models.ForeignKey(TentativaQuiz, on_delete=models.CASCADE, related_name='perguntas')
    pergunta = models.ForeignKey(Pergunta, on_delete=models.PROTECT, related_name='respostas')
    ordem = models.PositiveSmallIntegerField()
    opcao_escolhida = models.ForeignKey(Opcao, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    acertou = models.BooleanField(null=True, blank=True)

    class Meta:
        db_table = 'trilha_tentativas_perguntas'
        ordering = ['ordem']
        constraints = [
            models.UniqueConstraint(fields=['tentativa', 'pergunta'], name='pergunta_unica_por_tentativa'),
            models.UniqueConstraint(fields=['tentativa', 'ordem'], name='ordem_unica_por_tentativa'),
        ]


class Certificado(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey('users.Usuario', on_delete=models.CASCADE, related_name='certificados')
    trilha = models.ForeignKey(Trilha, on_delete=models.PROTECT, related_name='certificados')
    tentativa = models.OneToOneField(TentativaQuiz, on_delete=models.PROTECT, related_name='certificado')
    codigo = models.CharField(max_length=20, unique=True)
    nome_completo = models.CharField(max_length=205)
    emitido_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trilha_certificados'
        constraints = [models.UniqueConstraint(fields=['usuario', 'trilha'], name='certificado_unico_por_usuaria_e_trilha')]

    def __str__(self):
        return f'{self.codigo} {self.nome_completo}'
