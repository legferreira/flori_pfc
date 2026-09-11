# date: usado para converter a string de data recebida em objeto date
# (_validar_nascimento) e comparar com a data de hoje.
from datetime import date

# IntegrityError: exceção do Django/banco disparada quando uma constraint
#                 (ex: UNIQUE de email/celular) é violada no INSERT.
# transaction: fornece transaction.atomic(), garantindo que salvar o Usuario
#              e os Consentimentos aconteça tudo ou nada (ver _persistir).
from django.db import IntegrityError, transaction

# Objetos importados de models.py (mesma pasta 'users'):
# Consentimento e Usuario são as classes de model usadas/instanciadas abaixo.
from .models import Consentimento, Usuario

# Constantes de módulo: versão atual de cada documento legal, gravada em
# cada Consentimento criado (ver _registrar_consentimentos). Se o texto dos
# termos mudar, bastaria incrementar esta string para versionar o aceite.
VERSAO_TERMOS_USO = '1.0'
VERSAO_POLITICA_PRIVACIDADE = '1.0'


# Declaração de exceção customizada, herda de Exception (built-in do Python).
# Instanciada em vários pontos deste arquivo (ex: raise ErroCadastro('...'))
# e capturada em views.py (except ErroCadastro as e) para virar resposta HTTP.
class ErroCadastro(Exception):
    # Construtor: roda toda vez que 'ErroCadastro(...)' é instanciado.
    # mensagem -> texto amigável mostrado ao usuário/front-end.
    # status   -> código HTTP a devolver (400 por padrão; 409 em conflitos de duplicidade).
    def __init__(self, mensagem, status=400):
        super().__init__(mensagem)  # inicializa a Exception padrão do Python com a mensagem
        self.mensagem = mensagem    # guarda a mensagem como atributo, pra views.py ler via e.mensagem
        self.status = status        # guarda o status HTTP como atributo, pra views.py ler via e.status


class CadastroUsuario:
    """Cadastra uma usuária a partir dos dados crus da requisição.

    Cada regra vive em seu próprio método; `executar()` apenas define a ordem.
    """

    # Construtor: roda quando views.py faz CadastroUsuario(dados, ip_origem=...).
    # 'dados' é o dict decodificado do JSON enviado pelo front-end (cadastro.js -> payload).
    # Aqui SÓ extrai e normaliza os valores brutos em atributos da instância;
    # nenhuma validação de regra de negócio acontece ainda (isso é papel dos
    # métodos _validar_* chamados por executar()).
    def __init__(self, dados, ip_origem=None):
        self._dados = dados          # dict original, guardado para os métodos usarem .get()
        self.ip_origem = ip_origem   # IP calculado por views.ip_do_cliente(), repassado ao Consentimento
        # Cada linha abaixo declara/instancia um atributo de instância (self.<nome>),
        # lendo e limpando (strip) o respectivo campo do dict 'dados'.
        self.nome = self._texto('nome')
        self.sobrenome = self._texto('sobrenome')
        # Apelido é opcional: se não vier, usa o próprio nome como padrão.
        self.apelido = self._texto('apelido') or self.nome
        self.email = self._texto('email').lower() or None       # normaliza para minúsculas; string vazia vira None
        self.celular = self._texto('celular') or None            # string vazia vira None
        # Só aceita senha se vier como string; qualquer outro tipo (None, número, etc.) vira ''.
        self.senha = self._dados.get('senha') if isinstance(self._dados.get('senha'), str) else ''
        # bool(...) converte o valor recebido (ex: True/False/None/ausente) num booleano estrito.
        self.termos_aceitos = bool(self._dados.get('termos_aceitos'))
        self.data_nascimento = None  # definido em _validar_nascimento


#aqui estou orquestrando as etapas do cadastro, chamando os metodos de validacao e persistencia
    # Método público principal desta classe — é o único método chamado de fora
    # (por views.py: CadastroUsuario(dados, ...).executar()).
    # Roda cada validação em sequência (cada uma pode interromper tudo lançando
    # ErroCadastro) e, se todas passarem, chama _persistir() para gravar no banco.
    # Retorna a instância de Usuario criada por _persistir().
    def executar(self):
        self._validar_identificacao()
        self._validar_nascimento()
        self._validar_contato()
        self._validar_senha()
        self._validar_consentimento()
        return self._persistir()

    # Método utilitário privado (prefixo _ = convenção Python para "uso interno"):
    # lê um campo do dict self._dados e devolve a versão "limpa" (sem espaços
    # nas pontas). Se o valor não for string (ausente, None, número...), devolve ''.
    # Chamado várias vezes no __init__ acima.
    def _texto(self, campo):
        valor = self._dados.get(campo)
        return valor.strip() if isinstance(valor, str) else ''

    # --- regras de negócio  
    # Aqui separei as responsabilidades-------------------------------------------------

    # Cada _validar_* abaixo só LÊ atributos já preenchidos no __init__ e,
    # se a regra falhar, INTERROMPE o fluxo lançando ErroCadastro (a exceção
    # sobe direto para dentro de views.py, que a captura e vira resposta HTTP).
    # Se o método termina sem lançar nada, a regra passou.

    def _validar_identificacao(self):
        if not self.nome or not self.sobrenome:
            raise ErroCadastro('Nome e sobrenome são obrigatórios.')

    def _validar_nascimento(self):
        # Lê o valor bruto direto do dict original (ainda como string, ex: '2005-03-20').
        bruto = self._dados.get('data_nascimento')
        if not bruto:
            raise ErroCadastro('Data de nascimento é obrigatória.')

        try:
            # date.fromisoformat converte string 'AAAA-MM-DD' em objeto date.
            # Resultado é guardado em self.data_nascimento (atributo declarado
            # como None no __init__ e preenchido de verdade aqui).
            self.data_nascimento = date.fromisoformat(bruto)
        except (TypeError, ValueError):
            raise ErroCadastro('Data de nascimento inválida.')

        if self.data_nascimento > date.today():
            raise ErroCadastro('Data de nascimento não pode estar no futuro.')

        # Quem sabe a regra de idade é o próprio Usuario, não este serviço.
        # Instancia um Usuario TEMPORÁRIO (não salvo no banco, sem .save()) só
        # para reaproveitar o método tem_idade_minima() (definido em models.py),
        # que por sua vez usa a property idade e a constante IDADE_MINIMA.
        if not Usuario(data_nascimento=self.data_nascimento).tem_idade_minima():
            raise ErroCadastro('Ainda não é possível criar a conta com essa data de nascimento.')

    def _validar_contato(self):
        if not self.email and not self.celular:
            raise ErroCadastro('Informe pelo menos um contato: e-mail ou celular.')

    def _validar_senha(self):
        # Usuario.TAMANHO_MINIMO_SENHA é a constante de classe definida em models.py
        # (acessada aqui direto pela classe, sem precisar instanciar Usuario).
        if len(self.senha) < Usuario.TAMANHO_MINIMO_SENHA:
            raise ErroCadastro(
                f'A senha precisa ter pelo menos {Usuario.TAMANHO_MINIMO_SENHA} caracteres.'
            )

    def _validar_consentimento(self):
        if not self.termos_aceitos:
            raise ErroCadastro('É necessário aceitar os termos de uso.')

    # --- persistência aqui estou salvando as informacoes}_persistir() é a última etapa do executar(): é onde o cadastro e salvo no banco de dados------------------------------------------------------

    def _persistir(self):
        # Instanciação do model Usuario (models.py) em memória, com os dados
        # já validados pelos métodos _validar_*. Ainda NÃO existe no banco
        # até o .save() lá embaixo.
        usuario = Usuario(
            nome=self.nome,
            sobrenome=self.sobrenome,
            apelido=self.apelido,
            data_nascimento=self.data_nascimento,
            email=self.email,
            celular=self.celular,
        )
        # Chama o método de instância definir_senha() (models.py), que transforma
        # a senha em texto puro (self.senha) em hash e grava em usuario.senha_hash.
        usuario.definir_senha(self.senha)

        try:
            # transaction.atomic(): bloco 'with' que garante que TUDO dentro
            # dele vira um único INSERT em grupo — se qualquer linha falhar,
            # o Django desfaz (rollback) tudo, inclusive o usuario.save().
            # Evita criar um Usuario "órfão" sem seus Consentimentos.
            with transaction.atomic():
                usuario.save()  # INSERT de fato na tabela 'users' (gera usuario.id)
                self._registrar_consentimentos(usuario)
        except IntegrityError:
            # Disparado pelo banco quando email/celular já existem (constraint UNIQUE
            # dos campos, definida em models.py). _erro_de_duplicidade() descobre
            # qual dos dois e devolve o ErroCadastro apropriado.
            raise self._erro_de_duplicidade()

        return usuario

    def _registrar_consentimentos(self, usuario):
        # bulk_create: cria várias linhas de Consentimento em uma única operação
        # no banco (mais eficiente que dois .save() separados).
        # A list comprehension monta uma instância de Consentimento para cada
        # par (tipo, versão) da tupla abaixo — uma para termos de uso, outra
        # para política de privacidade — todas ligadas ao mesmo 'usuario'.
        Consentimento.objects.bulk_create([
            Consentimento(
                usuario=usuario,
                tipo=tipo,
                versao_documento=versao,
                aceito=True,
                ip_origem=self.ip_origem,
            )
            for tipo, versao in (
                (Consentimento.Tipo.TERMOS_USO, VERSAO_TERMOS_USO),
                (Consentimento.Tipo.POLITICA_PRIVACIDADE, VERSAO_POLITICA_PRIVACIDADE),
            )
        ])

    def _erro_de_duplicidade(self):
        """O banco recusou por UNIQUE — descobre qual contato já estava em uso."""
        # Usuario.objects é o "manager" padrão do Django (criado automaticamente
        # por herdar de models.Model): .filter(...).exists() consulta o banco
        # e devolve True/False sem carregar o registro inteiro.
        if self.email and Usuario.objects.filter(email=self.email).exists():
            return ErroCadastro('Esse e-mail já está em uso.', status=409)
        if self.celular and Usuario.objects.filter(celular=self.celular).exists():
            return ErroCadastro('Esse celular já está em uso.', status=409)
        # Nenhum dos dois bateu isoladamente: sobra alguma outra causa de
        # IntegrityError (ex: condição de corrida) — mensagem genérica.
        return ErroCadastro('Não foi possível concluir o cadastro.', status=409)
