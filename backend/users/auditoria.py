from .models import LogAtividade

CHAVES_SENSIVEIS = (
    'senha', 'senha_hash', 'token', 'chave', 'codigo_hash', 'codigo_2fa', 'desafio', 'id_token', 'email', 'celular',
)


def _sensivel(chave):
    chave = str(chave).lower()
    return any(chave == c or chave.startswith(f'{c}_') or chave.endswith(f'_{c}') for c in CHAVES_SENSIVEIS)


def limpar_resumo(valor):
    if isinstance(valor, dict):
        return {str(k): limpar_resumo(v) for k, v in valor.items() if not _sensivel(k)}
    if isinstance(valor, (list, tuple)):
        return [limpar_resumo(v) for v in valor]
    if valor is None or isinstance(valor, (bool, int, float)):
        return valor
    return str(valor)


def registrar_log(usuario, acao, ip=None, ator=None, alvo_tipo='', alvo_id='', resumo=None):
    return LogAtividade.objects.create(
        usuario=usuario,
        ator=ator,
        acao=acao,
        alvo_tipo=alvo_tipo or '',
        alvo_id=str(alvo_id or ''),
        resumo=limpar_resumo(resumo or {}),
        ip_origem=ip,
    )


def registrar_log_admin(ator, acao, alvo_tipo='', alvo_id='', resumo=None, ip=None):
    if not str(acao).startswith(LogAtividade.PREFIXO_ADMIN):
        raise ValueError(f'Ação administrativa inválida: {acao}')
    return registrar_log(ator, acao, ip=ip, ator=ator, alvo_tipo=alvo_tipo, alvo_id=alvo_id, resumo=resumo)


def diferenca(antes, depois):
    alterados = {k for k in depois if antes.get(k) != depois.get(k)}
    return {
        'antes': {k: antes.get(k) for k in sorted(alterados)},
        'depois': {k: depois.get(k) for k in sorted(alterados)},
    }
