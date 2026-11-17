from .models import AVISO_EXTRA, QUIZ_PERCENTUAL_APROVACAO


def fonte(f):
    return {'nome': f.nome, 'url': f.url}


def card(c, concluido_em=None):
    return {
        'id': str(c.id),
        'codigo': c.codigo,
        'tema': c.tema,
        'explicacao': c.explicacao,
        'exemplo': c.exemplo,
        'secoes': c.secoes,
        'cta': c.cta,
        'fontes': [fonte(f) for f in c.fontes.all()],
        'concluido': concluido_em is not None,
        'concluido_em': concluido_em.isoformat() if concluido_em else None,
    }


def assunto(a, conclusoes):
    cards = [card(c, conclusoes.get(c.id)) for c in a.cards.all()]
    feitos = sum(1 for c in cards if c['concluido'])
    return {
        'id': str(a.id), 'titulo': a.titulo, 'descricao': a.descricao, 'cor': a.cor,
        'cards': cards, 'concluidos': feitos, 'total': len(cards),
    }


def card_extra(c):
    return {**card(c), 'aviso': AVISO_EXTRA}


def extras(assuntos):
    return {
        'aviso': AVISO_EXTRA,
        'assuntos': [
            {
                'id': str(a.id), 'titulo': a.titulo, 'descricao': a.descricao, 'cor': a.cor,
                'cards': [card_extra(c) for c in a.cards.all()],
            }
            for a in assuntos
        ],
    }


def guia_rapido(g):
    return {
        'id': str(g.id), 'titulo': g.titulo, 'introducao': g.introducao, 'passos': list(g.passos),
        'fontes': [fonte(f) for f in g.fontes.all()],
    }


def certificado(c, trilha):
    if c is None:
        return None
    return {
        'codigo': c.codigo,
        'nome_completo': c.nome_completo,
        'trilha': trilha.nome,
        'carga_horaria_minutos': trilha.carga_horaria_minutos,
        'aproveitamento_percentual': c.tentativa.percentual,
        'emitido_em': c.emitido_em.isoformat(),
    }


def trilha_completa(r):
    trilha = r['trilha']
    concluida_em = r['trilha_concluida_em']
    return {
        'trilha': {
            'id': str(trilha.id), 'nome': trilha.nome,
            'carga_horaria_minutos': trilha.carga_horaria_minutos,
            'nota_minima_percentual': QUIZ_PERCENTUAL_APROVACAO,
        },
        'assuntos': [assunto(a, r['conclusoes']) for a in r['assuntos']],
        'concluidos': r['concluidos'],
        'total_cards': r['total_cards'],
        'trilha_concluida_em': concluida_em.isoformat() if concluida_em else None,
        'guias_rapidos': [guia_rapido(g) for g in r['guias_rapidos']],
        'quiz': r['quiz'],
        'certificado': certificado(r['certificado'], trilha),
        'modo_visualizacao': r['modo_visualizacao'],
    }


def pergunta(p):
    return {
        'id': str(p.id), 'enunciado': p.enunciado,
        'opcoes': [{'id': str(o.id), 'texto': o.texto} for o in p.opcoes.all()],
    }


def quiz(tentativa, perguntas):
    return {
        'tentativa_id': str(tentativa.id) if tentativa else None,
        'nota_minima_percentual': QUIZ_PERCENTUAL_APROVACAO,
        'total_perguntas': len(perguntas),
        'perguntas': [pergunta(p) for p in perguntas],
    }


def resultado_quiz(r):
    t = r['tentativa']
    return {
        'acertos': t.acertos, 'total_perguntas': t.total_perguntas, 'percentual': t.percentual,
        'aprovada': t.aprovada, 'nota_minima_percentual': QUIZ_PERCENTUAL_APROVACAO,
        'assuntos_a_revisar': [{'id': str(a.id), 'titulo': a.titulo} for a in r['assuntos_a_revisar']],
        'certificado': certificado(r['certificado'], r['trilha']),
    }
