import json
import re
import secrets
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone

from flori_backend.api import momento_iso
from trilha import serializers
from trilha.models import (
    AVISO_EXTRA, MENSAGEM_PERGUNTA_EXTRA, QUIZ_PERGUNTAS_POR_TENTATIVA, Assunto, Card, FonteCard, GuiaRapido, Opcao, Pergunta, ProgressoCard,
    TentativaPergunta,
)
from trilha.services import ErroTrilha, perguntas_visiveis, trilha_ativa
from users.auditoria import registrar_log_admin
from users.models import LogAtividade

SITUACOES = ('ativos', 'excluidos', 'todos')
LIMITE_RESUMO_LOG = 120
MENSAGEM_CAMPOS = 'Revise os campos destacados.'
MENSAGEM_CONFLITO = 'Este conteúdo foi alterado por outra pessoa. Recarregue para continuar.'
PALETA_ASSUNTOS = ('#EDBFD8', '#CDD98D', '#C9E372')
COR_HEX = re.compile(r'^#[0-9A-Fa-f]{6}$')
ESPACOS = re.compile(r'\s+')
MAXIMO_FONTES = 10
OPCOES_POR_PERGUNTA = 4
MAXIMO_PASSOS = 8
IMPACTO_EXTRA = 'não afeta progresso nem certificados'

LIMITES = {
    'assunto_titulo': 100,
    'assunto_descricao': 200,
    'card_titulo': 80,
    'card_explicacao': 600,
    'card_exemplo': 255,
    'fonte_nome': 120,
    'fonte_url': 300,
    'pergunta_enunciado': 200,
    'opcao_texto': 120,
    'guia_titulo': 80,
    'guia_passo': 200,
}


class ErroConteudo(ErroTrilha):
    pass


class Erros:
    def __init__(self):
        self.campos = {}

    def adicionar(self, campo, mensagem):
        self.campos.setdefault(campo, mensagem)

    def verificar(self, mensagem=MENSAGEM_CAMPOS):
        if self.campos:
            raise ErroConteudo(mensagem, status=400, campos=self.campos)


def ler_texto(dados, campo, rotulo, maximo, erros, obrigatorio=True, chave=None):
    chave = chave or campo
    valor = dados.get(campo) if isinstance(dados, dict) else None
    if valor is None:
        valor = ''
    if not isinstance(valor, str):
        erros.adicionar(chave, f'{rotulo} precisa ser um texto.')
        return ''
    texto = valor.strip()
    if obrigatorio and not texto:
        erros.adicionar(chave, f'Preencha {rotulo.lower()}.')
    elif len(texto) > maximo:
        erros.adicionar(chave, f'{rotulo} aceita no máximo {maximo} caracteres.')
    return texto


def url_valida(url):
    try:
        URLValidator(schemes=['http', 'https'])(url)
    except ValidationError:
        return False
    return True


def resumir(valor):
    texto = valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)
    return texto[:LIMITE_RESUMO_LOG]


def diferenca_resumida(antes, depois):
    campos = sorted(k for k in depois if antes.get(k) != depois.get(k))
    return {
        'campos': campos,
        'antes': {k: resumir(antes.get(k)) for k in campos},
        'depois': {k: resumir(depois.get(k)) for k in campos},
    }


def normalizar(texto):
    return ESPACOS.sub(' ', texto).strip().casefold()


def novo_codigo(model):
    while True:
        codigo = f'N{secrets.token_hex(4).upper()}'
        if not model.objects.filter(codigo=codigo).exists():
            return codigo


class GestorConteudo:
    model = None
    alvo_tipo = ''

    def __init__(self, ator, ip_origem=None):
        self.ator = ator
        self.ip_origem = ip_origem

    def base(self):
        return self.model.objects.all()

    def irmaos(self, objeto):
        raise NotImplementedError

    def validar(self, dados, objeto, ativo):
        raise NotImplementedError

    def aplicar(self, objeto, valores):
        raise NotImplementedError

    def salvar_filhos(self, objeto, valores):
        pass

    def preparar_novo(self, objeto, dados):
        pass

    def instantaneo(self, objeto):
        raise NotImplementedError

    def detalhar(self, objeto, situacao='ativos'):
        raise NotImplementedError

    def visualizar_objeto(self, objeto):
        raise NotImplementedError

    def impacto_objeto(self, objeto):
        raise NotImplementedError

    def antes_de_restaurar(self, objeto):
        pass

    def situacao(self, filtros):
        valor = (filtros.get('situacao') or 'ativos').strip()
        if valor not in SITUACOES:
            raise ErroConteudo('Situação inválida. Use ativos, excluidos ou todos.')
        return valor

    def ordenar(self, itens):
        return sorted(itens, key=lambda o: (o.excluido_em is not None, o.ordem, o.excluido_em or timezone.now()))

    def filtrar_lista(self, consulta, filtros):
        return consulta

    def listar(self, filtros):
        situacao = self.situacao(filtros)
        consulta = self.filtrar_lista(self.base().na_situacao(situacao), filtros)
        return [self.detalhar(o, situacao) for o in self.ordenar(consulta)]

    def obter(self, item_id, bloquear=False):
        consulta = self.base().select_for_update() if bloquear else self.base()
        objeto = consulta.filter(pk=item_id).first()
        if objeto is None:
            raise ErroConteudo('Conteúdo não encontrado.', status=404)
        return objeto

    def detalhe(self, item_id):
        return self.detalhar(self.obter(item_id), 'todos')

    def registrar(self, acao, objeto, resumo=None):
        registrar_log_admin(self.ator, acao, self.alvo_tipo, objeto.id, resumo or {}, self.ip_origem)

    def proxima_ordem(self, objeto):
        ultima = self.irmaos(objeto).exclude(pk=objeto.pk).order_by('-ordem').values_list('ordem', flat=True).first()
        return (ultima or 0) + 1

    def compactar(self, objeto):
        for ordem, item in enumerate(self.irmaos(objeto).order_by('ordem', 'atualizado_em'), start=1):
            if item.ordem != ordem:
                self.model.objects.filter(pk=item.pk).update(ordem=ordem)

    def criar(self, dados):
        if not isinstance(dados, dict):
            raise ErroConteudo('JSON inválido.')
        with transaction.atomic():
            objeto = self.model()
            self.preparar_novo(objeto, dados)
            objeto.ativo = dados.get('ativo') is not False
            valores = self.validar(dados, objeto, objeto.ativo)
            self.aplicar(objeto, valores)
            objeto.ordem = self.proxima_ordem(objeto)
            objeto.save()
            self.salvar_filhos(objeto, valores)
            self.registrar(LogAtividade.Acao.ADMIN_CONTEUDO_CRIADO, objeto, {
                'depois': {k: resumir(v) for k, v in self.instantaneo(objeto).items()},
            })
        return self.detalhe(objeto.id)

    def atualizar(self, item_id, dados):
        if not isinstance(dados, dict):
            raise ErroConteudo('JSON inválido.')
        with transaction.atomic():
            objeto = self.obter(item_id, bloquear=True)
            self.conferir_versao(objeto, dados)
            if objeto.excluido:
                raise ErroConteudo('Restaure este conteúdo antes de editar.', status=409)
            antes = self.instantaneo(objeto)
            valores = self.validar(dados, objeto, objeto.ativo)
            self.aplicar(objeto, valores)
            objeto.save()
            self.salvar_filhos(objeto, valores)
            depois = self.instantaneo(self.obter(item_id))
            if antes != depois:
                self.registrar(LogAtividade.Acao.ADMIN_CONTEUDO_EDITADO, objeto, diferenca_resumida(antes, depois))
        return self.detalhe(item_id)

    def conferir_versao(self, objeto, dados):
        lido = dados.get('atualizado_em')
        if not isinstance(lido, str) or not lido:
            raise ErroConteudo('Envie o atualizado_em lido do conteúdo.', campos={'atualizado_em': 'Obrigatório.'})
        try:
            momento = datetime.fromisoformat(lido)
        except ValueError:
            raise ErroConteudo('atualizado_em inválido.', campos={'atualizado_em': 'Data inválida.'})
        if timezone.is_naive(momento):
            momento = timezone.make_aware(momento)
        if momento != objeto.atualizado_em:
            raise ErroConteudo(MENSAGEM_CONFLITO, status=409)

    def dados_atuais(self, objeto):
        raise NotImplementedError

    def ativar(self, item_id):
        with transaction.atomic():
            objeto = self.obter(item_id, bloquear=True)
            if objeto.excluido:
                raise ErroConteudo('Restaure este conteúdo antes de ativar.', status=409)
            if objeto.ativo:
                return self.detalhe(item_id)
            try:
                self.validar(self.dados_atuais(objeto), objeto, True)
            except ErroConteudo as e:
                raise ErroConteudo('Corrija os campos e salve antes de ativar.', status=400, campos=e.campos)
            objeto.ativo = True
            objeto.save(update_fields=['ativo', 'atualizado_em'])
            self.registrar(LogAtividade.Acao.ADMIN_CONTEUDO_ATIVADO, objeto, self.resumo_curto(objeto))
        return self.detalhe(item_id)

    def desativar(self, item_id):
        with transaction.atomic():
            objeto = self.obter(item_id, bloquear=True)
            if objeto.excluido:
                raise ErroConteudo('Este conteúdo está excluído.', status=409)
            if not objeto.ativo:
                return self.detalhe(item_id)
            objeto.ativo = False
            objeto.save(update_fields=['ativo', 'atualizado_em'])
            self.registrar(LogAtividade.Acao.ADMIN_CONTEUDO_DESATIVADO, objeto, self.resumo_curto(objeto))
        return self.detalhe(item_id)

    def excluir(self, item_id):
        with transaction.atomic():
            objeto = self.obter(item_id, bloquear=True)
            if objeto.excluido:
                return self.detalhe(item_id)
            agora = timezone.now()
            objeto.excluido_em = agora
            objeto.save(update_fields=['excluido_em', 'atualizado_em'])
            extra = self.excluir_filhos(objeto, agora)
            self.compactar(objeto)
            self.registrar(LogAtividade.Acao.ADMIN_CONTEUDO_EXCLUIDO, objeto, {**self.resumo_curto(objeto), **extra})
        return self.detalhe(item_id)

    def excluir_filhos(self, objeto, momento):
        return {}

    def restaurar(self, item_id):
        with transaction.atomic():
            objeto = self.obter(item_id, bloquear=True)
            if not objeto.excluido:
                return self.detalhe(item_id)
            self.antes_de_restaurar(objeto)
            momento = objeto.excluido_em
            objeto.excluido_em = None
            objeto.ordem = self.proxima_ordem(objeto)
            objeto.save(update_fields=['excluido_em', 'ordem', 'atualizado_em'])
            extra = self.restaurar_filhos(objeto, momento)
            self.registrar(LogAtividade.Acao.ADMIN_CONTEUDO_RESTAURADO, objeto, {**self.resumo_curto(objeto), **extra})
        return self.detalhe(item_id)

    def restaurar_filhos(self, objeto, momento):
        return {}

    def reordenar(self, item_id, dados):
        direcao = dados.get('direcao') if isinstance(dados, dict) else None
        if direcao not in ('subir', 'descer'):
            raise ErroConteudo('Direção inválida. Use subir ou descer.')
        with transaction.atomic():
            objeto = self.obter(item_id, bloquear=True)
            if objeto.excluido:
                raise ErroConteudo('Restaure este conteúdo antes de reordenar.', status=409)
            self.compactar(objeto)
            lista = list(self.irmaos(objeto).select_for_update().order_by('ordem'))
            posicao = next(i for i, item in enumerate(lista) if item.pk == objeto.pk)
            vizinho = posicao - 1 if direcao == 'subir' else posicao + 1
            if not 0 <= vizinho < len(lista):
                raise ErroConteudo('Este item já está no limite da lista.')
            atual, outro = lista[posicao], lista[vizinho]
            self.model.objects.filter(pk=atual.pk).update(ordem=outro.ordem)
            self.model.objects.filter(pk=outro.pk).update(ordem=atual.ordem)
            self.registrar(LogAtividade.Acao.ADMIN_CONTEUDO_REORDENADO, objeto, {
                **self.resumo_curto(objeto), 'direcao': direcao, 'de': atual.ordem, 'para': outro.ordem,
            })
        return self.detalhe(item_id)

    def impacto(self, item_id):
        return self.impacto_objeto(self.obter(item_id))

    def visualizar(self, item_id):
        return {'modo_visualizacao': True, **self.visualizar_objeto(self.obter(item_id))}

    def resumo_curto(self, objeto):
        return {'titulo': resumir(str(objeto))}

    def estado(self, objeto):
        return {
            'ativo': objeto.ativo,
            'excluido_em': momento_iso(objeto.excluido_em),
            'atualizado_em': objeto.atualizado_em.isoformat(),
        }


class GestorAssunto(GestorConteudo):
    model = Assunto
    alvo_tipo = 'assunto'

    def base(self):
        return Assunto.objects.filter(trilha=trilha_ativa())

    def irmaos(self, objeto):
        return Assunto.objects.filter(trilha_id=objeto.trilha_id, tipo=objeto.tipo).nao_excluidos()

    def filtrar_lista(self, consulta, filtros):
        tipo = (filtros.get('tipo') or '').strip()
        if not tipo:
            return consulta
        if tipo not in Assunto.Tipo.values:
            raise ErroConteudo('Tipo inválido. Use oficial ou extra.', campos={'tipo': 'Use oficial ou extra.'})
        return consulta.filter(tipo=tipo)

    def preparar_novo(self, assunto, dados):
        tipo = dados.get('tipo', Assunto.Tipo.OFICIAL)
        if tipo not in Assunto.Tipo.values:
            raise ErroConteudo(MENSAGEM_CAMPOS, campos={'tipo': 'Use oficial ou extra.'})
        assunto.tipo = tipo
        assunto.trilha = trilha_ativa()
        assunto.cor = PALETA_ASSUNTOS[self.irmaos(assunto).count() % len(PALETA_ASSUNTOS)]

    def validar(self, dados, assunto, ativo):
        erros = Erros()
        if 'tipo' in dados and dados['tipo'] != assunto.tipo:
            erros.adicionar('tipo', 'O tipo do assunto é definido na criação e não pode ser alterado.')
        valores = {'titulo': ler_texto(dados, 'titulo', 'Nome do assunto', LIMITES['assunto_titulo'], erros)}
        if 'descricao' in dados:
            valores['descricao'] = ler_texto(
                dados, 'descricao', 'Descrição', LIMITES['assunto_descricao'], erros, obrigatorio=False,
            )
        if dados.get('cor'):
            cor = ler_texto(dados, 'cor', 'Cor', 7, erros)
            if not COR_HEX.match(cor):
                erros.adicionar('cor', 'Use uma cor no formato #RRGGBB.')
            valores['cor'] = cor.upper()
        erros.verificar()
        return valores

    def aplicar(self, assunto, valores):
        for campo, valor in valores.items():
            setattr(assunto, campo, valor)

    def dados_atuais(self, assunto):
        return {'titulo': assunto.titulo}

    def instantaneo(self, assunto):
        return {'titulo': assunto.titulo, 'descricao': assunto.descricao, 'cor': assunto.cor}

    def detalhar(self, assunto, situacao='ativos'):
        cards = Card.objects.filter(assunto=assunto).prefetch_related('fontes')
        if not assunto.excluido:
            cards = cards.na_situacao(situacao)
        cartoes = GestorCard(self.ator, self.ip_origem)
        return {
            'id': str(assunto.id), 'tipo': assunto.tipo, 'titulo': assunto.titulo, 'descricao': assunto.descricao,
            'cor': assunto.cor, 'ordem': assunto.ordem, **self.estado(assunto),
            'total_cards': Card.objects.filter(assunto=assunto).nao_excluidos().count(),
            'cards': [cartoes.detalhar(c) for c in cartoes.ordenar(cards)],
            **({'aviso': AVISO_EXTRA} if assunto.extra else {}),
        }

    def excluir_filhos(self, assunto, momento):
        quantidade = Card.objects.filter(assunto=assunto, excluido_em__isnull=True).update(
            excluido_em=momento, atualizado_em=momento,
        )
        return {'cards_excluidos': quantidade}

    def restaurar_filhos(self, assunto, momento):
        quantidade = Card.objects.filter(assunto=assunto, excluido_em=momento).update(
            excluido_em=None, atualizado_em=timezone.now(),
        )
        return {'cards_restaurados': quantidade}

    def impacto_objeto(self, assunto):
        impacto = {'cards': Card.objects.filter(assunto=assunto).nao_excluidos().count()}
        if assunto.extra:
            impacto['aviso'] = IMPACTO_EXTRA
        return impacto

    def visualizar_objeto(self, assunto):
        serializar = serializers.card_extra if assunto.extra else serializers.card
        cards = [serializar(c) for c in Card.objects.filter(assunto=assunto).visiveis().prefetch_related('fontes')]
        dados = {'assunto': {
            'id': str(assunto.id), 'tipo': assunto.tipo, 'titulo': assunto.titulo, 'descricao': assunto.descricao,
            'cor': assunto.cor, 'cards': cards, 'concluidos': 0, 'total': len(cards),
        }}
        if assunto.extra:
            dados['aviso'] = AVISO_EXTRA
        return dados


class GestorCard(GestorConteudo):
    model = Card
    alvo_tipo = 'card'

    def base(self):
        return Card.objects.filter(assunto__trilha=trilha_ativa()).select_related('assunto').prefetch_related('fontes')

    def irmaos(self, card):
        return Card.objects.filter(assunto_id=card.assunto_id).nao_excluidos()

    def filtrar_lista(self, consulta, filtros):
        if filtros.get('assunto'):
            try:
                consulta = consulta.filter(assunto_id=filtros['assunto'])
            except ValidationError:
                raise ErroConteudo('Assunto inválido.')
        return consulta

    def preparar_novo(self, card, dados):
        assunto = Assunto.objects.filter(trilha=trilha_ativa())
        try:
            assunto = assunto.filter(pk=dados.get('assunto_id')).first()
        except ValidationError:
            assunto = None
        if assunto is None:
            raise ErroConteudo('Assunto não encontrado.', campos={'assunto_id': 'Escolha um assunto.'})
        if assunto.excluido:
            raise ErroConteudo('Restaure o assunto antes', status=409)
        card.assunto = assunto
        card.codigo = novo_codigo(Card)

    def validar(self, dados, card, ativo):
        erros = Erros()
        valores = {
            'tema': ler_texto(dados, 'titulo', 'Título do card', LIMITES['card_titulo'], erros),
            'explicacao': ler_texto(dados, 'explicacao', 'Explicação', LIMITES['card_explicacao'], erros),
            'exemplo': ler_texto(dados, 'exemplo', 'Exemplo', LIMITES['card_exemplo'], erros, obrigatorio=False),
            'fontes': self._fontes(dados.get('fontes'), erros),
        }
        if ativo and not valores['fontes'] and 'fontes' not in erros.campos:
            erros.adicionar('fontes', 'Um card ativo precisa de pelo menos uma fonte.')
        erros.verificar()
        return valores

    def _fontes(self, lista, erros):
        if lista is None:
            lista = []
        if not isinstance(lista, list):
            erros.adicionar('fontes', 'Envie as fontes em uma lista.')
            return []
        if len(lista) > MAXIMO_FONTES:
            erros.adicionar('fontes', f'Use no máximo {MAXIMO_FONTES} fontes.')
            return []
        fontes = []
        for i, item in enumerate(lista):
            if not isinstance(item, dict):
                erros.adicionar(f'fontes.{i}.nome', 'Fonte inválida.')
                continue
            nome = ler_texto(item, 'nome', 'Nome da fonte', LIMITES['fonte_nome'], erros, chave=f'fontes.{i}.nome')
            url = ler_texto(item, 'url', 'Link da fonte', LIMITES['fonte_url'], erros, chave=f'fontes.{i}.url')
            if url and len(url) <= LIMITES['fonte_url'] and not url_valida(url):
                erros.adicionar(f'fontes.{i}.url', 'Use um link completo, começando com http:// ou https://.')
            fontes.append({'nome': nome, 'url': url})
        return fontes

    def aplicar(self, card, valores):
        card.tema = valores['tema']
        card.explicacao = valores['explicacao']
        card.exemplo = valores['exemplo']

    def salvar_filhos(self, card, valores):
        FonteCard.objects.filter(card=card).delete()
        FonteCard.objects.bulk_create(
            FonteCard(card=card, nome=f['nome'], url=f['url'], ordem=ordem)
            for ordem, f in enumerate(valores['fontes'], start=1)
        )

    def dados_atuais(self, card):
        return {
            'titulo': card.tema, 'explicacao': card.explicacao, 'exemplo': card.exemplo,
            'fontes': [{'nome': f.nome, 'url': f.url} for f in card.fontes.all()],
        }

    def instantaneo(self, card):
        return {**self.dados_atuais(card)}

    def antes_de_restaurar(self, card):
        if card.assunto.excluido:
            raise ErroConteudo('Restaure o assunto antes', status=409)

    def detalhar(self, card, situacao='ativos'):
        fontes = [{'nome': f.nome, 'url': f.url} for f in card.fontes.all()]
        return {
            'id': str(card.id), 'assunto_id': str(card.assunto_id), 'ordem': card.ordem,
            'titulo': card.tema, 'explicacao': card.explicacao, 'exemplo': card.exemplo,
            'fontes': fontes, 'total_fontes': len(fontes), **self.estado(card),
        }

    def impacto_objeto(self, card):
        impacto = {'pessoas_concluiram': ProgressoCard.objects.filter(card=card).values('usuario').distinct().count()}
        if card.assunto.extra:
            impacto['aviso'] = IMPACTO_EXTRA
        return impacto

    def visualizar_objeto(self, card):
        dados = {
            'assunto': {
                'id': str(card.assunto_id), 'tipo': card.assunto.tipo, 'titulo': card.assunto.titulo,
                'cor': card.assunto.cor,
            },
            'card': serializers.card_extra(card) if card.assunto.extra else serializers.card(card),
        }
        if card.assunto.extra:
            dados['aviso'] = AVISO_EXTRA
        return dados

    def resumo_curto(self, card):
        return {'titulo': resumir(card.tema)}


class GestorGuia(GestorConteudo):
    model = GuiaRapido
    alvo_tipo = 'guia'

    def irmaos(self, guia):
        return GuiaRapido.objects.nao_excluidos()

    def validar(self, dados, guia, ativo):
        erros = Erros()
        valores = {'titulo': ler_texto(dados, 'titulo', 'Título', LIMITES['guia_titulo'], erros)}
        passos = dados.get('passos')
        if not isinstance(passos, list) or not 1 <= len(passos) <= MAXIMO_PASSOS:
            erros.adicionar('passos', f'O guia precisa ter de 1 a {MAXIMO_PASSOS} passos.')
            passos = []
        valores['passos'] = [
            ler_texto({'passo': p}, 'passo', 'Passo', LIMITES['guia_passo'], erros, chave=f'passos.{i}')
            for i, p in enumerate(passos)
        ]
        erros.verificar()
        return valores

    def aplicar(self, guia, valores):
        guia.titulo = valores['titulo']
        guia.passos = valores['passos']

    def dados_atuais(self, guia):
        return {'titulo': guia.titulo, 'passos': list(guia.passos)}

    def instantaneo(self, guia):
        return self.dados_atuais(guia)

    def detalhar(self, guia, situacao='ativos'):
        return {
            'id': str(guia.id), 'ordem': guia.ordem, 'titulo': guia.titulo, 'passos': list(guia.passos),
            'total_passos': len(guia.passos), **self.estado(guia),
        }

    def impacto_objeto(self, guia):
        return {'passos': len(guia.passos)}

    def visualizar_objeto(self, guia):
        return {'guia': serializers.guia_rapido(guia)}


class GestorPergunta(GestorConteudo):
    model = Pergunta
    alvo_tipo = 'pergunta_quiz'

    def base(self):
        return Pergunta.objects.filter(trilha=trilha_ativa()).prefetch_related('opcoes')

    def irmaos(self, pergunta):
        return Pergunta.objects.filter(trilha_id=pergunta.trilha_id).nao_excluidos()

    def preparar_novo(self, pergunta, dados):
        pergunta.trilha = trilha_ativa()
        pergunta.codigo = novo_codigo(Pergunta)

    def validar(self, dados, pergunta, ativo):
        erros = Erros()
        valores = {'enunciado': ler_texto(dados, 'enunciado', 'Enunciado', LIMITES['pergunta_enunciado'], erros)}
        if 'assunto_id' in dados:
            valores['assunto'] = self._assunto(dados['assunto_id'], erros)
        opcoes = dados.get('opcoes')
        if not isinstance(opcoes, list) or len(opcoes) != OPCOES_POR_PERGUNTA:
            erros.adicionar('opcoes', f'A pergunta precisa ter exatamente {OPCOES_POR_PERGUNTA} opções.')
            erros.verificar()
        existentes = {str(o.id): o for o in pergunta.opcoes.all()} if pergunta.pk else {}
        limpas = []
        vistos = {}
        for i, item in enumerate(opcoes):
            if not isinstance(item, dict):
                erros.adicionar(f'opcoes.{i}.texto', 'Opção inválida.')
                continue
            texto = ler_texto(item, 'texto', 'Texto da opção', LIMITES['opcao_texto'], erros, chave=f'opcoes.{i}.texto')
            if texto:
                chave = normalizar(texto)
                if chave in vistos:
                    erros.adicionar(f'opcoes.{i}.texto', f'Esta opção repete a opção {"ABCD"[vistos[chave]]}.')
                vistos.setdefault(chave, i)
            opcao_id = item.get('id')
            if opcao_id and str(opcao_id) not in existentes:
                erros.adicionar(f'opcoes.{i}.id', 'Esta opção não pertence à pergunta.')
            if 'correta' in item and not isinstance(item['correta'], bool):
                erros.adicionar(f'opcoes.{i}.correta', 'Marque a correta com verdadeiro ou falso.')
            limpas.append({'id': str(opcao_id) if opcao_id else None, 'texto': texto, 'correta': item.get('correta') is True})
        ids = [o['id'] for o in limpas if o['id']]
        if len(ids) != len(set(ids)):
            erros.adicionar('opcoes', 'A mesma opção foi enviada duas vezes.')
        if sum(1 for o in limpas if o['correta']) != 1:
            erros.adicionar('opcoes', 'Marque exatamente uma opção correta.')
        erros.verificar()
        valores['opcoes'] = limpas
        return valores

    def _assunto(self, assunto_id, erros):
        if not assunto_id:
            return None
        try:
            assunto = Assunto.objects.filter(pk=assunto_id, trilha=trilha_ativa()).nao_excluidos().first()
        except ValidationError:
            assunto = None
        if assunto is None:
            erros.adicionar('assunto_id', 'Assunto não encontrado.')
        elif assunto.extra:
            erros.adicionar('assunto_id', MENSAGEM_PERGUNTA_EXTRA)
        return assunto

    def aplicar(self, pergunta, valores):
        pergunta.enunciado = valores['enunciado']
        if 'assunto' in valores:
            pergunta.assunto = valores['assunto']

    def salvar_filhos(self, pergunta, valores):
        existentes = {str(o.id): o for o in Opcao.objects.filter(pergunta=pergunta)}
        for deslocamento, opcao in enumerate(existentes.values(), start=1):
            Opcao.objects.filter(pk=opcao.pk).update(ordem=1000 + deslocamento)
        usados = set()
        for ordem, item in enumerate(valores['opcoes'], start=1):
            if item['id']:
                Opcao.objects.filter(pk=item['id']).update(texto=item['texto'], correta=item['correta'], ordem=ordem, ativo=True)
                usados.add(item['id'])
            else:
                Opcao.objects.create(pergunta=pergunta, texto=item['texto'], correta=item['correta'], ordem=ordem)
        sobras = [o for chave, o in existentes.items() if chave not in usados]
        for deslocamento, opcao in enumerate(sobras, start=1):
            Opcao.objects.filter(pk=opcao.pk).update(ativo=False, correta=False, ordem=100 + deslocamento)

    def dados_atuais(self, pergunta):
        return {
            'enunciado': pergunta.enunciado,
            'opcoes': [
                {'id': str(o.id), 'texto': o.texto, 'correta': o.correta}
                for o in Opcao.objects.filter(pergunta=pergunta, ativo=True).order_by('ordem')
            ],
        }

    def instantaneo(self, pergunta):
        atuais = self.dados_atuais(pergunta)
        return {
            'enunciado': atuais['enunciado'],
            'opcoes': [o['texto'] for o in atuais['opcoes']],
            'correta': next((o['texto'] for o in atuais['opcoes'] if o['correta']), ''),
        }

    def detalhar(self, pergunta, situacao='ativos'):
        opcoes = self.dados_atuais(pergunta)['opcoes']
        return {
            'id': str(pergunta.id), 'ordem': pergunta.ordem, 'enunciado': pergunta.enunciado, 'opcoes': opcoes,
            'assunto_id': str(pergunta.assunto_id) if pergunta.assunto_id else None,
            'correta': next((o['texto'] for o in opcoes if o['correta']), None), **self.estado(pergunta),
        }

    def impacto_objeto(self, pergunta):
        respostas = TentativaPergunta.objects.filter(pergunta=pergunta, acertou__isnull=False)
        return {'pessoas_responderam': respostas.values('tentativa__usuario').distinct().count()}

    def visualizar_objeto(self, pergunta):
        opcoes = Opcao.objects.filter(pergunta=pergunta, ativo=True).order_by('ordem')
        return {'pergunta': {
            'id': str(pergunta.id), 'enunciado': pergunta.enunciado,
            'opcoes': [{'id': str(o.id), 'texto': o.texto} for o in opcoes],
        }}

    def resumo_curto(self, pergunta):
        return {'titulo': resumir(pergunta.enunciado)}


def resumo_do_quiz():
    trilha = trilha_ativa()
    ativas = perguntas_visiveis(trilha).count()
    return {
        'cadastradas': Pergunta.objects.filter(trilha=trilha).nao_excluidos().count(),
        'ativas': ativas,
        'por_tentativa': min(QUIZ_PERGUNTAS_POR_TENTATIVA, ativas),
    }


GESTORES = {
    'assuntos': GestorAssunto,
    'cards': GestorCard,
    'guias': GestorGuia,
    'perguntas': GestorPergunta,
}

ACOES_POST = ('ativar', 'desativar', 'excluir', 'restaurar', 'reordenar')
ACOES_GET = ('impacto', 'visualizar')


def gestor(recurso, ator, ip_origem=None):
    classe = GESTORES.get(recurso)
    if classe is None:
        raise ErroConteudo('Tipo de conteúdo inválido.', status=404)
    return classe(ator, ip_origem)
