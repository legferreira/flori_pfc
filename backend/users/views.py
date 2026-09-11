# --- Imports ------------------------------------------------------------
# json: usado para decodificar o corpo (body) da requisição HTTP, que chega
#       como texto puro e precisa virar dict Python (json.loads).
import json

# settings: acesso às configurações globais do projeto (flori_backend/settings.py),
#           usado aqui só para ler a flag CONFIA_EM_X_FORWARDED_FOR.
from django.conf import settings
# JsonResponse: classe do Django que monta uma resposta HTTP com Content-Type
#               application/json a partir de um dict Python.
from django.http import JsonResponse
# method_decorator: adapta um decorator feito para função (como csrf_exempt)
#                    para funcionar em cima de um método de classe (dispatch).
from django.utils.decorators import method_decorator
# View: classe base do Django para criar views baseadas em classe (CBV).
#       Cada verbo HTTP (get, post, etc.) vira um método da subclasse.
from django.views import View
# csrf_exempt: decorator que desliga a checagem de token CSRF nesta view
#              (necessário aqui pois a API é consumida por JS puro, sem cookie de sessão).
from django.views.decorators.csrf import csrf_exempt

# Objetos importados de services.py (mesma pasta 'users'):
# - CadastroUsuario: classe de serviço que concentra a regra de cadastro
#   (declarada e documentada em users/services.py).
# - ErroCadastro: exceção customizada usada para sinalizar erro de validação/negócio.
from .services import CadastroUsuario, ErroCadastro


# --- Funções utilitárias (helpers) de resposta HTTP ----------------------
# Não são classes nem métodos de objeto: são funções soltas do módulo,
# reaproveitadas pelas views abaixo para padronizar o formato das respostas.

def resposta_json(dados, status=200):
    """Monta uma resposta JSON padronizada.

    Parâmetros:
      dados  -> dict que vira o corpo (body) da resposta.
      status -> código HTTP (200 por padrão).
    Retorna um objeto JsonResponse (instanciado aqui dentro, na linha de baixo).
    ensure_ascii=False permite acentos/caracteres em português na resposta,
    em vez de serem convertidos para sequências \\uXXXX.
    """
    return JsonResponse(dados, status=status, json_dumps_params={'ensure_ascii': False})


def erro(mensagem, status=400):
    """Atalho para respostas de erro: reaproveita resposta_json() acima,
    sempre no formato {'mensagem': '...'}. status=400 (Bad Request) é o padrão.
    """
    return resposta_json({'mensagem': mensagem}, status=status)


def ip_do_cliente(request):
    """IP para o registro de consentimento.

    X-Forwarded-For é forjável pelo cliente: só vale quando há um proxy confiável
    na frente reescrevendo o header. Por isso depende de um setting explícito.
    """
    # getattr com default False: se o setting não existir no settings.py,
    # assume que NÃO confiamos no header (comportamento seguro por padrão).
    if getattr(settings, 'CONFIA_EM_X_FORWARDED_FOR', False):
        # request.META é um dict com os headers/metadados da requisição HTTP.
        # HTTP_X_FORWARDED_FOR é o header que um proxy/load balancer usa para
        # informar o IP original do cliente (pode conter uma lista "ip1, ip2, ...").
        encaminhado = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if encaminhado:
            # Pega só o primeiro IP da lista (o mais próximo do cliente real).
            return encaminhado.split(',')[0].strip()
    # Caminho padrão: IP direto da conexão TCP, sem depender de headers forjáveis.
    return request.META.get('REMOTE_ADDR')


# --- View (classe baseada em View do Django) -----------------------------
# @method_decorator aplica csrf_exempt ao método especial 'dispatch' da classe,
# que é o método interno do Django que roteia a requisição para get/post/etc.
# Ou seja: isso desliga a exigência de CSRF token para TODOS os métodos desta view.
@method_decorator(csrf_exempt, name='dispatch')
class CadastroUsuarioView(View):
    """View HTTP para o endpoint POST /api/usuarios.

    Declarada aqui; instanciada automaticamente pelo Django a cada requisição
    (View.as_view(), usado em users/urls.py, cria uma nova instância por request).
    Não guarda estado entre requisições — cada post() é independente.
    """

    # Método chamado automaticamente pelo Django quando chega uma requisição
    # HTTP POST para a URL associada a esta view (ver users/urls.py).
    # 'self' é a instância da view; 'request' é o objeto HttpRequest do Django.
    def post(self, request):
        # request.body: bytes crus do corpo da requisição.
        # json.loads: tenta converter esses bytes/texto em um dict/list Python.
        try:
            dados = json.loads(request.body)
        except ValueError:
            # JSON malformado (sintaxe inválida) cai aqui.
            return erro('JSON inválido.')

        # Garante que o JSON enviado é um objeto ({...}) e não, por exemplo,
        # uma lista ou um número solto.
        if not isinstance(dados, dict):
            return erro('JSON inválido.')

        try:
            # Instanciação do objeto de serviço CadastroUsuario (definido em services.py),
            # passando os dados brutos do formulário e o IP calculado por ip_do_cliente().
            # .executar() é o método que roda todas as validações e persiste no banco
            # (retorna a instância de Usuario criada, ou lança ErroCadastro).
            usuario = CadastroUsuario(dados, ip_origem=ip_do_cliente(request)).executar()
        except ErroCadastro as e:
            # Erro de validação/negócio: devolve a mensagem e o status definidos
            # na própria exceção (ex: 400 para dados inválidos, 409 para duplicidade).
            return erro(e.mensagem, status=e.status)

        # Sucesso (201 Created): devolve só o id e o apelido do usuário criado,
        # nunca dados sensíveis como senha_hash.
        return resposta_json({'id': usuario.id, 'apelido': usuario.apelido}, status=201)
