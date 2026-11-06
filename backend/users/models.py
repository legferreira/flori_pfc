from datetime import date, datetime
import hashlib
import secrets
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models


def _sha256(texto):
    return hashlib.sha256(texto.encode()).hexdigest()


class Usuario(models.Model):
    IDADE_MINIMA = 13
    TAMANHO_MINIMO_SENHA = 8

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100)
    sobrenome = models.CharField(max_length=100)
    apelido = models.CharField(max_length=50, blank=True)
    data_nascimento = models.CharField(max_length=10)
    email = models.EmailField(max_length=150, unique=True, null=True, blank=True, db_collation='utf8mb4_bin')
    celular = models.CharField(max_length=20, unique=True, null=True, blank=True)
    senha_hash = models.CharField(max_length=255)
    foto_url = models.URLField(max_length=500, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.apelido

    @property
    def idade(self):
        nascimento = datetime.strptime(self.data_nascimento, '%d/%m/%Y').date()
        hoje = date.today()
        idade = hoje.year - nascimento.year
        if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
            idade -= 1
        return idade

    def consentimentos_atuais(self):
        atuais = {}
        for c in self.consentimentos.order_by('data_consentimento'):
            atuais[c.tipo] = c
        return atuais

    def tem_consentimento_revogado(self):
        return any(not c.aceito for c in self.consentimentos_atuais().values())

    def tem_idade_minima(self):
        return self.idade >= self.IDADE_MINIMA

    def definir_senha(self, senha_pura):
        self.senha_hash = make_password(senha_pura)

    def definir_sem_senha(self):
        self.senha_hash = make_password(None)

    def verificar_senha(self, senha_pura):
        return check_password(senha_pura, self.senha_hash)


class Consentimento(models.Model):
    class Tipo(models.TextChoices):
        TERMOS_USO = 'termos_uso', 'Termos de uso'
        POLITICA_PRIVACIDADE = 'politica_privacidade', 'Política de privacidade'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name='consentimentos'
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    versao_documento = models.CharField(max_length=20)
    aceito = models.BooleanField()
    data_consentimento = models.DateTimeField(auto_now_add=True)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'consentimentos'
        indexes = [models.Index(fields=['usuario', 'tipo', '-data_consentimento'])]

    def __str__(self):
        return f'{self.usuario.apelido} — {self.get_tipo_display()} v{self.versao_documento}'


class Token(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chave = models.CharField(max_length=64, unique=True, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='tokens')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tokens'

    def save(self, *args, **kwargs):
        if not self.chave:
            self.chave = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.usuario.apelido} — token'


class LogAtividade(models.Model):
    class Acao(models.TextChoices):
        CADASTRO = 'cadastro', 'Cadastro realizado'
        LOGIN_SUCESSO = 'login_sucesso', 'Login com sucesso'
        LOGIN_FALHA = 'login_falha', 'Tentativa de login falhou'
        REDEFINICAO_SENHA_SOLICITADA = 'redefinicao_senha_solicitada', 'Redefinição de senha solicitada'
        SENHA_REDEFINIDA = 'senha_redefinida', 'Senha redefinida'
        CODIGO_2FA_ENVIADO = 'codigo_2fa_enviado', 'Código de verificação enviado'
        CODIGO_2FA_INVALIDO = 'codigo_2fa_invalido', 'Código de verificação inválido'
        LOGIN_GOOGLE = 'login_google', 'Login com Google'
        LOGOUT = 'logout', 'Saiu da conta'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs'
    )
    acao = models.CharField(max_length=30, choices=Acao.choices)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'logs_atividade'
        indexes = [models.Index(fields=['usuario', '-criado_em'])]

    def __str__(self):
        quem = self.usuario.apelido if self.usuario else 'desconhecida'
        return f'{quem} — {self.get_acao_display()} em {self.criado_em}'


class SolicitacaoRedefinicaoSenha(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=150)
    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, null=True, blank=True,
        related_name='solicitacoes_redefinicao_senha',
    )
    token_hash = models.CharField(max_length=64, unique=True, null=True, blank=True)
    expira_em = models.DateTimeField(null=True, blank=True)
    usado_em = models.DateTimeField(null=True, blank=True)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'solicitacoes_redefinicao_senha'
        indexes = [models.Index(fields=['email', '-criado_em'])]

    @staticmethod
    def gerar_hash(token):
        return _sha256(token)

    def __str__(self):
        return f'{self.email} — redefinição de senha em {self.criado_em}'


class CodigoAutenticacao(models.Model):
    QUANTIDADE_DIGITOS = 6
    VALIDADE_MINUTOS = 15
    MAXIMO_TENTATIVAS = 5

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='codigos_autenticacao')
    desafio_hash = models.CharField(max_length=64, unique=True)
    codigo_hash = models.CharField(max_length=255)
    tentativas = models.PositiveSmallIntegerField(default=0)
    expira_em = models.DateTimeField()
    usado_em = models.DateTimeField(null=True, blank=True)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'codigos_autenticacao'
        indexes = [models.Index(fields=['usuario', '-criado_em'])]

    @staticmethod
    def gerar_hash_desafio(desafio):
        return _sha256(desafio)

    def definir_codigo(self, codigo):
        self.codigo_hash = make_password(codigo)

    def confere(self, codigo):
        return check_password(codigo, self.codigo_hash)

    def pode_ser_usado(self, agora):
        return (
            self.usado_em is None
            and self.expira_em > agora
            and self.tentativas < self.MAXIMO_TENTATIVAS
        )

    def __str__(self):
        return f'{self.usuario.apelido} — código 2FA em {self.criado_em}'
