from datetime import date, datetime, time, timedelta
import logging

from django.core.paginator import Paginator
from django.db.models import Count, Exists, F, Max, OuterRef, Q
from django.utils import timezone

from flori_backend.api import momento_iso
from trilha.models import Assunto, ProgressoCard, ProgressoTrilha, TentativaQuiz, Trilha
from trilha.services import cards_visiveis, percentual
from users.auditoria import registrar_log, registrar_log_admin
from users.models import Consentimento, LogAtividade, Usuario
from users.notificacoes import NotificacaoService
from users.services import ErroServico, ExcluirConta, mascarar_email

logger = logging.getLogger(__name__)

TAMANHO_MAXIMO_OBSERVACAO = 140
MOTIVOS_EXCLUSAO = ('pedido_titular', 'violacao_termos', 'conta_duplicada', 'conta_teste', 'outro')
ACOES_LOGIN = (LogAtividade.Acao.LOGIN_SUCESSO, LogAtividade.Acao.LOGIN_GOOGLE)


class ConsultarDashboardAdmin:
    DIAS_PADRAO = 30
    DIAS_MAXIMO = 366

    def __init__(self, ator, filtros=None, ip_origem=None):
        filtros = filtros or {}
        self.ator = ator
        self.ip_origem = ip_origem
        self.de_bruto = (filtros.get('de') or '').strip()
        self.ate_bruto = (filtros.get('ate') or '').strip()

    def executar(self):
        de, ate = self._periodo()
        inicio = timezone.make_aware(datetime.combine(de, time.min))
        fim = timezone.make_aware(datetime.combine(ate + timedelta(days=1), time.min))

        users = Usuario.objects.filter(perfil=Usuario.Perfil.USER)
        ativas = set(users.ativos().values_list('id', flat=True))
        trilha = Trilha.objects.filter(ativa=True).first()
        progresso = ProgressoCard.objects.filter(usuario_id__in=ativas)
        if trilha is not None:
            progresso = progresso.filter(card__assunto__trilha=trilha, card__assunto__tipo=Assunto.Tipo.OFICIAL)
        else:
            progresso = progresso.none()
        iniciaram_alguma_vez = set(progresso.values_list('usuario_id', flat=True))
        concluiram_alguma_vez = set(
            ProgressoTrilha.objects.filter(
                trilha=trilha, usuario_id__in=ativas, trilha_concluida_em__isnull=False,
            ).values_list('usuario_id', flat=True)
        ) if trilha is not None else set()
        finalizadas = TentativaQuiz.objects.filter(usuario_id__in=ativas, finalizada_em__isnull=False)

        entraram = set(
            LogAtividade.objects.filter(
                acao__in=ACOES_LOGIN, criado_em__gte=inicio, criado_em__lt=fim, usuario_id__in=ativas,
            ).values_list('usuario_id', flat=True)
        )
        iniciaram = entraram & iniciaram_alguma_vez
        concluiram = iniciaram & concluiram_alguma_vez
        tentaram = concluiram & set(finalizadas.values_list('usuario_id', flat=True))
        aprovadas = tentaram & set(finalizadas.filter(aprovada=True).values_list('usuario_id', flat=True))

        cadastros = list(users.filter(criado_em__gte=inicio, criado_em__lt=fim).values_list('criado_em', flat=True))
        dados = {
            'periodo': {'de': de.isoformat(), 'ate': ate.isoformat(), 'dias': (ate - de).days + 1},
            'cadastros_no_periodo': len(cadastros),
            'entraram_no_periodo': len(entraram),
            'contas_cadastradas': len(ativas),
            'funil': {
                'entraram': len(entraram),
                'iniciaram_trilha': len(iniciaram),
                'concluiram_cards': len(concluiram),
                'tentaram_quiz': len(tentaram),
                'aprovadas_quiz': len(aprovadas),
            },
            'avisos_periodo': {
                'contas_excluidas': users.filter(excluido_em__gte=inicio, excluido_em__lt=fim).count(),
                'consentimentos_revogados': Consentimento.objects.filter(
                    usuario__perfil=Usuario.Perfil.USER, aceito=False,
                    data_consentimento__gte=inicio, data_consentimento__lt=fim,
                ).count(),
            },
            'situacao_contas': self._situacao(ativas, iniciaram_alguma_vez, concluiram_alguma_vez),
            'conclusao_por_card': self._conclusao_por_card(trilha, progresso, iniciaram_alguma_vez),
            'cadastros_por_semana': self._semanas(de, ate, cadastros),
        }
        registrar_log_admin(
            self.ator, LogAtividade.Acao.ADMIN_CONSULTOU_DASHBOARD, 'dashboard', '',
            {'de': dados['periodo']['de'], 'ate': dados['periodo']['ate']}, self.ip_origem,
        )
        return dados

    def _periodo(self):
        hoje = timezone.localdate()
        erros = {}
        datas = {}
        for nome, bruto in (('de', self.de_bruto), ('ate', self.ate_bruto)):
            if not bruto:
                continue
            try:
                datas[nome] = date.fromisoformat(bruto)
            except ValueError:
                erros[nome] = 'Use uma data válida no formato AAAA-MM-DD.'
        if erros:
            raise ErroServico('Revise o período.', campos=erros)
        ate = datas.get('ate', hoje)
        de = datas.get('de', ate - timedelta(days=self.DIAS_PADRAO - 1))
        if de > ate:
            raise ErroServico('Revise o período.', campos={'de': 'A data inicial precisa ser igual ou anterior à final.'})
        if (ate - de).days + 1 > self.DIAS_MAXIMO:
            raise ErroServico('Revise o período.', campos={'ate': f'Escolha um período de até {self.DIAS_MAXIMO} dias.'})
        return de, ate

    @staticmethod
    def _percentual(parte, total):
        return round(parte * 100 / total, 1) if total else 0.0

    def _situacao(self, ativas, iniciaram, concluiram):
        total = len(ativas)
        concluidas = len(concluiram & ativas)
        andamento = len((iniciaram & ativas) - concluiram)
        grupos = (
            ('concluiram', concluidas),
            ('em_andamento', andamento),
            ('nao_iniciaram', total - concluidas - andamento),
        )
        return {
            'total': total,
            'grupos': [{'chave': chave, 'contas': n, 'percentual': self._percentual(n, total)} for chave, n in grupos],
        }

    def _conclusao_por_card(self, trilha, progresso, iniciaram):
        if trilha is None:
            return {'base': 0, 'cards': []}
        cards = list(cards_visiveis(trilha).select_related('assunto').order_by('assunto__ordem', 'ordem'))
        por_card = dict(
            progresso.filter(card__in=cards).values_list('card').annotate(n=Count('usuario', distinct=True))
        )
        base = len(iniciaram)
        return {
            'base': base,
            'cards': [
                {
                    'numero': numero, 'titulo': card.tema, 'assunto_id': str(card.assunto_id),
                    'assunto': card.assunto.titulo, 'contas': por_card.get(card.id, 0),
                    'percentual': percentual(por_card.get(card.id, 0), base),
                }
                for numero, card in enumerate(cards, start=1)
            ],
        }

    @staticmethod
    def _semanas(de, ate, cadastros):
        dias = [timezone.localtime(momento).date() for momento in cadastros]
        segunda = de - timedelta(days=de.weekday())
        semanas = []
        while segunda <= ate:
            domingo = segunda + timedelta(days=6)
            semanas.append({
                'inicio': segunda.isoformat(),
                'rotulo': segunda.strftime('%d/%m'),
                'cadastros': sum(1 for d in dias if segunda <= d <= domingo),
            })
            segunda += timedelta(days=7)
        return semanas


class ListarUsuarios:
    POR_PAGINA = 20
    SITUACOES = ('ativas', 'excluidas', 'todas')
    ORDENS = {
        'cadastro_desc': ('-criado_em',),
        'cadastro_asc': ('criado_em',),
        'entrada_desc': (F('ultima_entrada').desc(nulls_last=True), '-criado_em'),
    }

    def __init__(self, ator, filtros=None, ip_origem=None):
        filtros = filtros or {}
        self.ator = ator
        self.ip_origem = ip_origem
        self.busca = (filtros.get('busca') or '').strip()
        self.situacao = (filtros.get('situacao') or '').strip() or 'ativas'
        self.ordem = (filtros.get('ordem') or '').strip() or 'cadastro_desc'
        self.pagina = filtros.get('pagina') or 1

    def executar(self):
        erros = {}
        if self.situacao not in self.SITUACOES:
            erros['situacao'] = 'Use ativas, excluidas ou todas.'
        if self.ordem not in self.ORDENS:
            erros['ordem'] = 'Use cadastro_desc, cadastro_asc ou entrada_desc.'
        if len(self.busca) > 50:
            erros['busca'] = 'Busque com no máximo 50 caracteres.'
        if erros:
            raise ErroServico('Revise os filtros.', campos=erros)

        trilha = Trilha.objects.filter(ativa=True).first()
        visiveis = list(cards_visiveis(trilha).values_list('id', flat=True)) if trilha else []
        paginador = Paginator(self._consulta(visiveis), self.POR_PAGINA)
        pagina = paginador.get_page(self.pagina)
        registrar_log_admin(
            self.ator, LogAtividade.Acao.ADMIN_LISTOU_USUARIOS, 'usuario', '',
            {'pagina': pagina.number, 'situacao': self.situacao, 'ordem': self.ordem, 'com_busca': bool(self.busca)},
            self.ip_origem,
        )
        return {
            'pagina': pagina.number,
            'por_pagina': self.POR_PAGINA,
            'total': paginador.count,
            'total_paginas': paginador.num_pages,
            'itens': [self._serializar(u, len(visiveis)) for u in pagina],
        }

    def _consulta(self, visiveis):
        usuarios = Usuario.objects.all()
        if self.situacao == 'ativas':
            usuarios = usuarios.ativos()
        elif self.situacao == 'excluidas':
            usuarios = usuarios.excluidos()
        if self.busca:
            usuarios = usuarios.filter(apelido__icontains=self.busca)
        tentativas = TentativaQuiz.objects.filter(usuario=OuterRef('pk'), finalizada_em__isnull=False)
        return usuarios.annotate(
            cards_concluidos=Count('progresso_trilha', filter=Q(progresso_trilha__card_id__in=visiveis), distinct=True),
            ultima_entrada=Max('logs__criado_em', filter=Q(logs__acao__in=ACOES_LOGIN)),
            tentou_quiz=Exists(tentativas),
            aprovada_quiz=Exists(tentativas.filter(aprovada=True)),
        ).order_by(*self.ORDENS[self.ordem])

    @staticmethod
    def _quiz(usuario):
        if usuario.aprovada_quiz:
            return 'aprovada'
        return 'nao_aprovada' if usuario.tentou_quiz else 'nao_tentou'

    def _serializar(self, usuario, total_cards):
        excluida = not usuario.ativo
        com_progresso = not excluida and not usuario.is_admin
        return {
            'id': str(usuario.id),
            'apelido': usuario.apelido,
            'email_mascarado': mascarar_email(usuario.email) if usuario.email else None,
            'cadastro': momento_iso(usuario.criado_em),
            'perfil': usuario.perfil,
            'trilha': {'concluidos': usuario.cards_concluidos, 'total': total_cards} if com_progresso else None,
            'quiz': self._quiz(usuario) if com_progresso else None,
            'ultima_entrada': None if excluida else momento_iso(usuario.ultima_entrada),
            'situacao': 'excluida' if excluida else 'ativa',
            'excluida_em': momento_iso(usuario.excluido_em),
            'demo': usuario.demo,
        }


class ExcluirUsuarioAdmin:
    def __init__(self, ator, usuario_id, dados, ip_origem=None):
        self.ator = ator
        self.usuario_id = usuario_id
        motivo = dados.get('motivo')
        self.motivo = motivo.strip() if isinstance(motivo, str) else ''
        observacao = dados.get('observacao')
        self.observacao = observacao.strip() if isinstance(observacao, str) else ''
        self.observacao_invalida = observacao is not None and not isinstance(observacao, str)
        self.ip_origem = ip_origem

    def executar(self):
        erros = {}
        if self.motivo not in MOTIVOS_EXCLUSAO:
            erros['motivo'] = 'Escolha um motivo da lista.'
        if self.observacao_invalida:
            erros['observacao'] = 'A observação precisa ser um texto.'
        elif len(self.observacao) > TAMANHO_MAXIMO_OBSERVACAO:
            erros['observacao'] = f'Use no máximo {TAMANHO_MAXIMO_OBSERVACAO} caracteres.'
        if erros:
            raise ErroServico('Revise os campos destacados.', campos=erros)
        if str(self.usuario_id) == str(self.ator.id):
            raise ErroServico('Você não pode excluir a própria conta por aqui.', status=403)
        alvo = Usuario.objects.filter(pk=self.usuario_id).first()
        if alvo is None:
            raise ErroServico('Conta não encontrada.', status=404)
        if alvo.is_admin:
            raise ErroServico('Conta admin é protegida e não pode ser excluída.', status=403)
        if not alvo.ativo:
            raise ErroServico('Essa conta já foi excluída.', status=409)
        contato = ExcluirConta(self.usuario_id, ip_origem=self.ip_origem, ator=self.ator, motivo=self.motivo).executar()
        if contato is None:
            raise ErroServico('Essa conta já foi excluída.', status=409)
        if contato['email']:
            self._avisar(contato)

    def _avisar(self, contato):
        try:
            NotificacaoService().enviar_conta_excluida(contato['email'], contato['apelido'], pelo_admin=True)
        except Exception:
            logger.exception('Falha ao enviar aviso de exclusão de conta feita pelo admin')
            registrar_log(
                Usuario.objects.get(pk=contato['id']), LogAtividade.Acao.EXCLUSAO_AVISO_FALHOU, self.ip_origem,
                ator=self.ator, alvo_tipo='usuario', alvo_id=contato['id'],
                resumo={'destino': mascarar_email(contato['email'])},
            )

