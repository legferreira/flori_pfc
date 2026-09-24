
from datetime import date, datetime

from django.contrib.auth.hashers import check_password, make_password

from django.db import models

import uuid

import secrets

import hashlib



class Usuario(models.Model):
    """Dados da usuária e as regras que dependem apenas deles."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

   
    IDADE_MINIMA = 13          # usada em tem_idade_minima() e por CadastroUsuario._validar_nascimento (services.py)
    TAMANHO_MINIMO_SENHA = 8   # usada por CadastroUsuario._validar_senha (services.py)

   
    nome = models.CharField(max_length=100)
    sobrenome = models.CharField(max_length=100)
    apelido = models.CharField(max_length=50, blank=True)
    data_nascimento = models.CharField(max_length=10)
    email = models.EmailField(max_length=150, unique=True, null=True, blank=True)
    celular = models.CharField(max_length=20, unique=True, null=True, blank=True)
    senha_hash = models.CharField(max_length=255)
    # Foto do perfil Google (campo 'picture' do token). Só existe para quem
    # entrou/cadastrou pelo Google; atualizada a cada login com Google.
    foto_url = models.URLField(max_length=500, null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)


    class Meta:
        db_table = 'users'

    
    def __str__(self):
        return self.apelido

    @property
    def idade(self):
        """Derivada da data de nascimento (texto 'DD/MM/AAAA'). Nunca armazenada como número: idade guardada envelhece errado."""
        nascimento = datetime.strptime(self.data_nascimento, '%d/%m/%Y').date()
        hoje = date.today()
        idade = hoje.year - nascimento.year
        # Se ainda não chegou o mês/dia do aniversário este ano, subtrai 1
        # (comparação de tuplas (mês, dia)
        if (hoje.month, hoje.day) < (nascimento.month, nascimento.day):
            idade -= 1
        return idade

  
    def tem_idade_minima(self):
        return self.idade >= self.IDADE_MINIMA

  
    def definir_senha(self, senha_pura):
        self.senha_hash = make_password(senha_pura)

    # Conta criada pelo Google, sem senha: make_password(None) gera um valor
    # que check_password nunca aceita, login por senha fica impossível até
    # a usuária criar uma em "Esqueci minha senha".
    def definir_sem_senha(self):
        self.senha_hash = make_password(None)


    def verificar_senha(self, senha_pura):
        return check_password(senha_pura, self.senha_hash)


class Consentimento(models.Model):
    """Aceite datado e versionado — a prova de consentimento que a LGPD exige (Art. 8º, §1º).

    Uma usuária tem vários ao longo do tempo: cada aceite ou revogação vira uma linha nova,
    e nenhuma é sobrescrita. É por isso que isso não cabia num booleano em Usuario.
    """

    
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
    # Preenchido automaticamente na criação (mesmo mecanismo de Usuario.criado_em).
    data_consentimento = models.DateTimeField(auto_now_add=True)
    # Guarda o IP de quem consentiu (calculado em views.py -> ip_do_cliente()),
    # opcional pois nem sempre é possível obter (null=True, blank=True).
    ip_origem = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'consentimentos'
        indexes = [models.Index(fields=['usuario', 'tipo', '-data_consentimento'])]

    def __str__(self):
        return f'{self.usuario.apelido} — {self.get_tipo_display()} v{self.versao_documento}'


class Token(models.Model):
    """Token de sessão emitido no login — comprova que a requisição vem de uma usuária autenticada."""

   
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
    """Registro de auditoria: quem fez o quê e quando (cadastro, login).

    Item de entrega separado do Consentimento — este é log técnico/operacional,
    não prova legal de consentimento, mas segue o mesmo espírito de nunca
    sobrescrever, só acumular linhas novas.
    """

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
    """Cada pedido de "esqueci a senha" — serve de trava de reenvio e guarda o token provisório.

    Registra o pedido pelo E-MAIL digitado, exista ou não uma usuária com ele:
    assim o intervalo de espera é o mesmo nos dois casos e a resposta da API
    não revela quais e-mails estão cadastrados (enumeração de usuárias).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=150)
    
    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, null=True, blank=True,
        related_name='solicitacoes_redefinicao_senha',
    )
    # Só o hash SHA-256 do token vai para o banco 
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
        return hashlib.sha256(token.encode()).hexdigest()

    def __str__(self):
        return f'{self.email} — redefinição de senha em {self.criado_em}'


class CodigoAutenticacao(models.Model):
    """Código de 6 dígitos da autenticação em dois fatores (2FA), enviado por e-mail no login.

    Depois que contato + senha conferem, o login fica "pendente" até a usuária
    digitar o código. O 'desafio' identifica esse login pendente: o front-end
    recebe o desafio em texto e o reenvia junto com o código na verificação.
    """

    VALIDADE_MINUTOS = 15
    MAXIMO_TENTATIVAS = 5

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='codigos_autenticacao')
    # Como o token de redefinição de senha: só o hash SHA-256 fica no banco.
    desafio_hash = models.CharField(max_length=64, unique=True)
    # Hash do código (mesmo make_password das senhas) — o código em texto só existe no e-mail.
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
        return hashlib.sha256(desafio.encode()).hexdigest()

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