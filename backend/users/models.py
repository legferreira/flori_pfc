from datetime import date, datetime
import hashlib
import secrets
import uuid

from django.contrib.auth.hashers import check_password, is_password_usable, make_password
from django.db import models
from django.utils import timezone


def _sha256(texto):
    return hashlib.sha256(texto.encode()).hexdigest()


class AdminProtegido(Exception):
    def __init__(self, mensagem='Conta admin não pode ser excluída.'):
        super().__init__(mensagem)
        self.mensagem = mensagem


class ExclusaoFisicaProibida(Exception):
    def __init__(self, mensagem='Contas não são apagadas fisicamente. Use a exclusão de conta.'):
        super().__init__(mensagem)
        self.mensagem = mensagem


class LogImutavel(Exception):
    pass


class UsuarioQuerySet(models.QuerySet):
    def admins(self):
        return self.filter(perfil=Usuario.Perfil.ADMIN)

    def ativos(self):
        return self.filter(ativo=True)

    def excluidos(self):
        return self.filter(ativo=False)

    def delete(self):
        if self.admins().exists():
            raise AdminProtegido()
        raise ExclusaoFisicaProibida()

    def apagar_demo_definitivo(self):
        if self.admins().exists():
            raise AdminProtegido()
        if self.exclude(demo=True).exists():
            raise ExclusaoFisicaProibida('Só contas de demonstração podem ser apagadas fisicamente.')
        return models.QuerySet.delete(self)


class Usuario(models.Model):
    IDADE_MINIMA = 13
    TAMANHO_MINIMO_SENHA = 8

    class Perfil(models.TextChoices):
        USER = 'user', 'User'
        ADMIN = 'admin', 'Admin'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100)
    sobrenome = models.CharField(max_length=100)
    apelido = models.CharField(max_length=50, blank=True)
    data_nascimento = models.CharField(max_length=10)
    email = models.EmailField(max_length=150, unique=True, null=True, blank=True, db_collation='utf8mb4_bin')
    celular = models.CharField(max_length=20, unique=True, null=True, blank=True)
    senha_hash = models.CharField(max_length=255)
    foto_url = models.URLField(max_length=500, null=True, blank=True)
    perfil = models.CharField(max_length=10, choices=Perfil.choices, default=Perfil.USER)
    situacao_menstrual = models.CharField(max_length=20, null=True, blank=True)
    demo = models.BooleanField(default=False, editable=False)
    ativo = models.BooleanField(default=True)
    excluido_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    NOME_EXCLUIDO = 'Conta excluída'
    NASCIMENTO_EXCLUIDO = '01/01/1900'

    objects = UsuarioQuerySet.as_manager()

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.apelido

    @property
    def is_admin(self):
        return self.perfil == self.Perfil.ADMIN

    def save(self, *args, **kwargs):
        campos = kwargs.get('update_fields')
        if not self._state.adding and not self.is_admin and (campos is None or 'perfil' in campos):
            era_admin = Usuario.objects.filter(pk=self.pk, perfil=self.Perfil.ADMIN).exists()
            if era_admin and not Usuario.objects.admins().exclude(pk=self.pk).exists():
                raise AdminProtegido('O último admin não pode ser rebaixado.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.is_admin or Usuario.objects.filter(pk=self.pk, perfil=self.Perfil.ADMIN).exists():
            raise AdminProtegido()
        raise ExclusaoFisicaProibida()

    def anonimizar(self, agora):
        self.ativo = False
        self.excluido_em = agora
        self.nome = self.sobrenome = self.apelido = self.NOME_EXCLUIDO
        self.email = None
        self.celular = None
        self.data_nascimento = self.NASCIMENTO_EXCLUIDO
        self.foto_url = None
        self.situacao_menstrual = None
        self.definir_sem_senha()

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
        return any(not c.aceito for tipo, c in self.consentimentos_atuais().items() if tipo in Consentimento.DOCUMENTOS)

    def consentimento_saude_ativo(self):
        atual = self.consentimentos_atuais().get(Consentimento.Tipo.SAUDE)
        return bool(atual and atual.aceito)

    @property
    def diario_disponivel(self):
        from diario.constantes import SITUACOES_COM_DIARIO

        return not self.is_admin and self.situacao_menstrual in SITUACOES_COM_DIARIO

    def tem_idade_minima(self):
        return self.idade >= self.IDADE_MINIMA

    def definir_senha(self, senha_pura):
        self.senha_hash = make_password(senha_pura)

    def definir_sem_senha(self):
        self.senha_hash = make_password(None)

    def verificar_senha(self, senha_pura):
        return check_password(senha_pura, self.senha_hash)

    def tem_senha(self):
        return is_password_usable(self.senha_hash)


class Consentimento(models.Model):
    class Tipo(models.TextChoices):
        TERMOS_USO = 'termos_uso', 'Termos de uso'
        POLITICA_PRIVACIDADE = 'politica_privacidade', 'Política de privacidade'
        SAUDE = 'saude', 'Dados de saúde'

    DOCUMENTOS = (Tipo.TERMOS_USO, Tipo.POLITICA_PRIVACIDADE)

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


class LogAtividadeQuerySet(models.QuerySet):
    def administrativos(self):
        return self.filter(acao__startswith=LogAtividade.PREFIXO_ADMIN)

    def comuns(self):
        return self.exclude(acao__startswith=LogAtividade.PREFIXO_ADMIN)

    def update(self, **kwargs):
        raise LogImutavel('Logs não podem ser alterados.')

    def delete(self):
        raise LogImutavel('Logs não podem ser apagados.')

    def anonimizar_ip(self):
        return models.QuerySet.update(self, ip_origem=None)


class LogAtividade(models.Model):
    PREFIXO_ADMIN = 'admin_'

    class Acao(models.TextChoices):
        CADASTRO = 'cadastro', 'Cadastro realizado'
        LOGIN_SUCESSO = 'login_sucesso', 'Login com sucesso'
        LOGIN_FALHA = 'login_falha', 'Tentativa de login falhou'
        LOGIN_BLOQUEADO = 'login_bloqueado', 'Login bloqueado temporariamente'
        REDEFINICAO_SENHA_SOLICITADA = 'redefinicao_senha_solicitada', 'Redefinição de senha solicitada'
        SENHA_REDEFINIDA = 'senha_redefinida', 'Senha redefinida'
        CODIGO_2FA_ENVIADO = 'codigo_2fa_enviado', 'Código de verificação enviado'
        CODIGO_2FA_INVALIDO = 'codigo_2fa_invalido', 'Código de verificação inválido'
        LOGIN_GOOGLE = 'login_google', 'Login com Google'
        LOGOUT = 'logout', 'Saiu da conta'
        PERFIL_ATUALIZADO = 'perfil_atualizado', 'Perfil atualizado'
        CONSENTIMENTO_REVOGADO = 'consentimento_revogado', 'Consentimento revogado'
        CONSENTIMENTO_REATIVADO = 'consentimento_reativado', 'Consentimento reativado'
        EXPORTACAO_DADOS = 'exportacao_dados', 'Exportação dos dados'
        EXCLUSAO_CONTA_PROPRIA = 'exclusao_conta_propria', 'Conta excluída pela própria pessoa'
        EXCLUSAO_CONTA_RECUSADA = 'exclusao_conta_recusada', 'Exclusão de conta recusada'
        EXCLUSAO_CONTA_DEMO = 'exclusao_conta_demo', 'Conta de demonstração removida'
        EMAIL_ALTERACAO_SOLICITADA = 'email_alteracao_solicitada', 'Troca de email solicitada'
        EMAIL_ALTERACAO_RECUSADA = 'email_alteracao_recusada', 'Troca de email recusada'
        EMAIL_ALTERACAO_CODIGO_INVALIDO = 'email_alteracao_codigo_invalido', 'Código de troca de email inválido'
        EMAIL_ALTERACAO_EXPIRADA = 'email_alteracao_expirada', 'Troca de email expirada'
        EMAIL_ALTERADO = 'email_alterado', 'Email alterado'
        EMAIL_ALTERADO_AVISO_FALHOU = 'email_alterado_aviso_falhou', 'Aviso de troca de email não enviado'
        EXCLUSAO_AVISO_FALHOU = 'exclusao_aviso_falhou', 'Aviso de exclusão de conta não enviado'
        DOCUMENTOS_ACEITOS = 'documentos_aceitos', 'Novas versões dos documentos aceitas'
        PROGRESSO_ADMIN_LIMPO = 'progresso_admin_limpo', 'Progresso de contas admin apagado'
        ADMIN_CRIADO = 'admin_criado', 'Admin criado ou promovido'
        ADMIN_LOGIN = 'admin_login', 'Login de admin'
        ADMIN_CONSULTOU_DASHBOARD = 'admin_consultou_dashboard', 'Admin consultou o dashboard'
        ADMIN_CONSULTOU_LOGS = 'admin_consultou_logs', 'Admin consultou os logs'
        ADMIN_LISTOU_USUARIOS = 'admin_listou_usuarios', 'Admin listou users'
        ADMIN_EXCLUIU_USUARIO = 'admin_excluiu_usuario', 'Admin excluiu user'
        ADMIN_USER_EXCLUIDO = 'admin_user_excluido', 'Admin excluiu a conta de um user'
        ADMIN_CRIOU_CONTEUDO = 'admin_criou_conteudo', 'Admin criou conteúdo'
        ADMIN_EDITOU_CONTEUDO = 'admin_editou_conteudo', 'Admin editou conteúdo'
        ADMIN_DESATIVOU_CONTEUDO = 'admin_desativou_conteudo', 'Admin desativou conteúdo'
        ADMIN_ACESSO_NEGADO = 'admin_acesso_negado', 'Acesso admin negado'
        ADMIN_CONTEUDO_CRIADO = 'admin_conteudo_criado', 'Admin criou conteúdo'
        ADMIN_CONTEUDO_EDITADO = 'admin_conteudo_editado', 'Admin editou conteúdo'
        ADMIN_CONTEUDO_ATIVADO = 'admin_conteudo_ativado', 'Admin ativou conteúdo'
        ADMIN_CONTEUDO_DESATIVADO = 'admin_conteudo_desativado', 'Admin desativou conteúdo'
        ADMIN_CONTEUDO_EXCLUIDO = 'admin_conteudo_excluido', 'Admin excluiu conteúdo'
        ADMIN_CONTEUDO_RESTAURADO = 'admin_conteudo_restaurado', 'Admin restaurou conteúdo'
        ADMIN_CONTEUDO_REORDENADO = 'admin_conteudo_reordenado', 'Admin reordenou conteúdo'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs'
    )
    ator = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs_como_ator'
    )
    acao = models.CharField(max_length=40, choices=Acao.choices)
    alvo_tipo = models.CharField(max_length=30, blank=True, default='')
    alvo_id = models.CharField(max_length=64, blank=True, default='')
    resumo = models.JSONField(default=dict, blank=True)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    criado_em = models.DateTimeField(default=timezone.now, editable=False)

    objects = LogAtividadeQuerySet.as_manager()

    class Meta:
        db_table = 'logs_atividade'
        indexes = [
            models.Index(fields=['usuario', '-criado_em']),
            models.Index(fields=['acao', '-criado_em']),
        ]

    def __str__(self):
        quem = self.usuario.apelido if self.usuario else 'desconhecida'
        return f'{quem} — {self.get_acao_display()} em {self.criado_em}'

    @property
    def administrativo(self):
        return self.acao.startswith(self.PREFIXO_ADMIN)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise LogImutavel('Logs não podem ser alterados.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise LogImutavel('Logs não podem ser apagados.')


class TentativaLogin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contato_hash = models.CharField(max_length=64, db_index=True)
    ip_origem = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'tentativas_login'

    @staticmethod
    def gerar_hash(contato):
        return _sha256(contato.strip().lower())


class TrocaEmailPendente(models.Model):
    VALIDADE_MINUTOS = 15
    MAXIMO_TENTATIVAS = 5

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='troca_email_pendente')
    email_novo = models.EmailField(max_length=150)
    codigo_hash = models.CharField(max_length=255)
    tentativas = models.PositiveSmallIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()

    class Meta:
        db_table = 'trocas_email_pendentes'

    def definir_codigo(self, codigo):
        self.codigo_hash = make_password(codigo)

    def confere(self, codigo):
        return check_password(codigo, self.codigo_hash)

    def expirada(self, agora):
        return self.expira_em <= agora

    def __str__(self):
        return f'{self.usuario.apelido}, troca de email pendente'


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
