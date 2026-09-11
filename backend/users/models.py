# date: usado para calcular idade a partir da data de nascimento (property 'idade' abaixo).
from datetime import date

# check_password/make_password: funções do Django para gerar e comparar hash
# de senha (usam o algoritmo configurado em AUTH_PASSWORD_VALIDATORS/settings).
# Nunca guardamos a senha em texto puro — só o hash (campo senha_hash abaixo).
from django.contrib.auth.hashers import check_password, make_password
# models: módulo do Django com as classes base para models (models.Model),
#         tipos de campo (CharField, DateField, etc.) e utilitários (Index, TextChoices).
from django.db import models


# Declaração da classe/model Usuario. Por herdar de models.Model, o Django
# cria automaticamente uma tabela no banco (ver Meta.db_table abaixo) com
# uma coluna para cada atributo de classe do tipo models.<Campo>.
# Instâncias desta classe são criadas em services.py (CadastroUsuario._persistir)
# e em views.py (indiretamente, via usuario = CadastroUsuario(...).executar()).
class Usuario(models.Model):
    """Dados da usuária e as regras que dependem apenas deles."""

    # --- Constantes de classe (não são campos de banco, são regras fixas) ---
    IDADE_MINIMA = 13          # usada em tem_idade_minima() e por CadastroUsuario._validar_nascimento (services.py)
    TAMANHO_MINIMO_SENHA = 8   # usada por CadastroUsuario._validar_senha (services.py)

    # --- Campos (colunas da tabela 'users') ----------------------------
    # Cada linha abaixo declara uma coluna do banco de dados.
    nome = models.CharField(max_length=100)
    sobrenome = models.CharField(max_length=100)
    apelido = models.CharField(max_length=50)
    data_nascimento = models.DateField()
    # unique=True -> o banco recusa dois usuários com o mesmo e-mail (gera
    # IntegrityError, tratado em services.py em _persistir/_erro_de_duplicidade).
    # null=True, blank=True -> campo opcional (pode ser vazio, já que email OU celular basta).
    email = models.EmailField(max_length=150, unique=True, null=True, blank=True)
    celular = models.CharField(max_length=20, unique=True, null=True, blank=True)
    # Nunca recebe a senha em texto puro diretamente: só é preenchido via
    # definir_senha() abaixo, que já grava o hash.
    senha_hash = models.CharField(max_length=255)
    # auto_now_add=True -> preenchido automaticamente pelo Django com a data/hora
    # atual no momento da criação (INSERT); não pode ser editado depois.
    criado_em = models.DateTimeField(auto_now_add=True)

    # Metadados do model (não vira campo/coluna): configurações da tabela em si.
    class Meta:
        # A tabela continua 'users' (schema_users.sql) — nome neutro, decisão de projeto.
        db_table = 'users'

    # Método especial do Python: define como a instância aparece quando
    # convertida para string (ex: no admin do Django, em print(), em logs).
    def __str__(self):
        return self.apelido

    # @property transforma o método abaixo num atributo somente-leitura:
    # chama-se como usuario.idade (sem parênteses), não usuario.idade().
    @property
    def idade(self):
        """Derivada da data de nascimento. Nunca armazenada: idade guardada envelhece errado."""
        hoje = date.today()
        idade = hoje.year - self.data_nascimento.year
        # Se ainda não chegou o mês/dia do aniversário este ano, subtrai 1
        # (comparação de tuplas (mês, dia), funciona como comparação lexicográfica).
        if (hoje.month, hoje.day) < (self.data_nascimento.month, self.data_nascimento.day):
            idade -= 1
        return idade

    # Método de instância: usa self.idade (a property acima) e a constante
    # de classe IDADE_MINIMA. Chamado por services.py (_validar_nascimento).
    def tem_idade_minima(self):
        return self.idade >= self.IDADE_MINIMA

    # Recebe a senha em texto puro (só existe na memória, nunca é salva assim)
    # e grava o hash resultante no campo senha_hash. Chamado em
    # services.py -> CadastroUsuario._persistir().
    def definir_senha(self, senha_pura):
        self.senha_hash = make_password(senha_pura)

    # Compara uma senha em texto puro com o hash já salvo (usado num futuro
    # fluxo de login; login.js ainda não está integrado ao back-end).
    def verificar_senha(self, senha_pura):
        return check_password(senha_pura, self.senha_hash)


class Consentimento(models.Model):
    """Aceite datado e versionado — a prova de consentimento que a LGPD exige (Art. 8º, §1º).

    Uma usuária tem vários ao longo do tempo: cada aceite ou revogação vira uma linha nova,
    e nenhuma é sobrescrita. É por isso que isso não cabia num booleano em Usuario.
    """

    # Subclasse de TextChoices: declara um "enum" de valores válidos para o
    # campo 'tipo' abaixo. Cada linha é (valor_salvo_no_banco, rótulo_legível).
    # Usado em services.py como Consentimento.Tipo.TERMOS_USO / .POLITICA_PRIVACIDADE.
    class Tipo(models.TextChoices):
        TERMOS_USO = 'termos_uso', 'Termos de uso'
        POLITICA_PRIVACIDADE = 'politica_privacidade', 'Política de privacidade'

    # --- Campos (colunas da tabela 'consentimentos') --------------------
    # ForeignKey: cada linha de Consentimento pertence a um Usuario (chave estrangeira).
    # on_delete=models.PROTECT -> impede apagar um Usuario que tenha consentimentos
    # registrados (protege o histórico exigido pela LGPD).
    # related_name='consentimentos' -> permite acessar, a partir de uma instância
    # de Usuario, todos os seus registros via usuario.consentimentos.all().
    usuario = models.ForeignKey(
        Usuario, on_delete=models.PROTECT, related_name='consentimentos'
    )
    # choices=Tipo.choices -> restringe os valores aceitos aos definidos na classe Tipo acima.
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
        # Index composto: acelera consultas que filtram por usuário+tipo
        # ordenando pelo consentimento mais recente primeiro ('-' = decrescente).
        indexes = [models.Index(fields=['usuario', 'tipo', '-data_consentimento'])]

    # Representação em texto da instância (usada em logs, admin, debug).
    # get_tipo_display() é um método gerado automaticamente pelo Django para
    # todo campo com 'choices': devolve o rótulo legível (ex: 'Termos de uso')
    # em vez do valor salvo no banco (ex: 'termos_uso').
    def __str__(self):
        return f'{self.usuario.apelido} — {self.get_tipo_display()} v{self.versao_documento}'
