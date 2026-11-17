import uuid

from django.db import models


class Sintoma(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=30, unique=True)
    nome = models.CharField(max_length=60)
    ativo = models.BooleanField(default=True)
    ordem = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = 'diario_sintomas'
        ordering = ['ordem', 'nome']

    def __str__(self):
        return self.nome


class RegistroDiario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey('users.Usuario', on_delete=models.CASCADE, related_name='registros_diario')
    data = models.DateField()
    fluxo = models.CharField(max_length=10, null=True, blank=True)
    humor = models.CharField(max_length=10, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'diario_registros'
        ordering = ['data']
        constraints = [models.UniqueConstraint(fields=['usuario', 'data'], name='registro_diario_unico_por_dia')]


class RegistroSintoma(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registro = models.ForeignKey(RegistroDiario, on_delete=models.CASCADE, related_name='sintomas')
    sintoma = models.ForeignKey(Sintoma, on_delete=models.PROTECT, related_name='registros')
    intensidade = models.CharField(max_length=10)

    class Meta:
        db_table = 'diario_registros_sintomas'
        constraints = [models.UniqueConstraint(fields=['registro', 'sintoma'], name='sintoma_unico_por_registro')]
