import uuid

from django.db import models
from django.utils import timezone


class Fonte(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=200)
    url = models.URLField(max_length=255, unique=True)

    class Meta:
        db_table = 'trilha_fontes'

    def __str__(self):
        return self.nome


class Trilha(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=120)
    carga_horaria_minutos = models.PositiveSmallIntegerField(default=60)
    nota_minima_percentual = models.PositiveSmallIntegerField(default=70)
    ativa = models.BooleanField(default=True)

    class Meta:
        db_table = 'trilhas'

    def __str__(self):
        return self.nome


class Assunto(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trilha = models.ForeignKey(Trilha, on_delete=models.CASCADE, related_name='assuntos')
    titulo = models.CharField(max_length=100)
    descricao = models.CharField(max_length=200)
    cor = models.CharField(max_length=7, help_text='Cor da marca em hexadecimal, ex: #EDBFD8')
    ordem = models.PositiveSmallIntegerField()

    class Meta:
        db_table = 'trilha_assuntos'
        ordering = ['ordem']
        constraints = [models.UniqueConstraint(fields=['trilha', 'ordem'], name='assunto_ordem_unica_por_trilha')]

    def __str__(self):
        return self.titulo


class Card(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assunto = models.ForeignKey(Assunto, on_delete=models.CASCADE, related_name='cards')
    codigo = models.CharField(max_length=10, unique=True)
    tema = models.CharField(max_length=100)
    explicacao = models.TextField()
    exemplo = models.CharField(max_length=255, blank=True)
    secoes = models.JSONField(default=list, blank=True)
    cta = models.CharField(max_length=255, blank=True)
    ordem = models.PositiveSmallIntegerField()
    fontes = models.ManyToManyField(Fonte, related_name='cards')

    class Meta:
        db_table = 'trilha_cards'
        ordering = ['ordem']
        constraints = [models.UniqueConstraint(fields=['assunto', 'ordem'], name='card_ordem_unica_por_assunto')]

    def __str__(self):
        return f'{self.codigo} {self.tema}'


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


class GuiaRapido(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=100)
    introducao = models.CharField(max_length=255)
    passos = models.JSONField(default=list)
    fontes = models.ManyToManyField(Fonte, related_name='guias_rapidos')
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'trilha_guias_rapidos'

    def __str__(self):
        return self.titulo


class Pergunta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trilha = models.ForeignKey(Trilha, on_delete=models.CASCADE, related_name='perguntas')
    assunto = models.ForeignKey(Assunto, on_delete=models.PROTECT, related_name='perguntas')
    codigo = models.CharField(max_length=10, unique=True)
    enunciado = models.CharField(max_length=255)
    ordem = models.PositiveSmallIntegerField()

    class Meta:
        db_table = 'trilha_perguntas'
        ordering = ['ordem']

    def __str__(self):
        return self.enunciado


class Opcao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pergunta = models.ForeignKey(Pergunta, on_delete=models.CASCADE, related_name='opcoes')
    texto = models.CharField(max_length=200)
    correta = models.BooleanField(default=False)
    ordem = models.PositiveSmallIntegerField()

    class Meta:
        db_table = 'trilha_opcoes'
        ordering = ['ordem']

    def __str__(self):
        return self.texto


class TentativaQuiz(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey('users.Usuario', on_delete=models.CASCADE, related_name='tentativas_quiz')
    trilha = models.ForeignKey(Trilha, on_delete=models.CASCADE, related_name='tentativas')
    acertos = models.PositiveSmallIntegerField()
    total = models.PositiveSmallIntegerField()
    percentual = models.PositiveSmallIntegerField()
    aprovada = models.BooleanField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trilha_tentativas_quiz'
        indexes = [models.Index(fields=['usuario', 'trilha', '-criado_em'])]

    def __str__(self):
        return f'{self.usuario.apelido}: {self.acertos}/{self.total}'


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
