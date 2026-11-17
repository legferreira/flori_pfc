import re
from collections import Counter
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from . import constantes as c
from .models import RegistroDiario, RegistroSintoma, Sintoma

FORMATO_MES = re.compile(r'^(\d{4})-(\d{2})$')
CAMPOS_ACEITOS = {'fluxo', 'humor', 'sintomas'}


class ErroDiario(Exception):
    def __init__(self, mensagem, status=400, campos=None, codigo=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status
        self.campos = campos
        self.codigo = codigo


def hoje():
    return timezone.localdate()


def exigir_acesso(usuario, disponibilidade=True):
    if not usuario.consentimento_saude_ativo():
        raise ErroDiario(c.MENSAGEM_CONSENTIMENTO_SAUDE, status=403, codigo='consentimento_saude_necessario')
    if disponibilidade and not usuario.diario_disponivel:
        raise ErroDiario(c.MENSAGEM_DIARIO_INDISPONIVEL, status=403, codigo='diario_indisponivel')


def ler_dia(texto):
    try:
        dia = date.fromisoformat(texto)
    except (TypeError, ValueError):
        raise ErroDiario('Data inválida. Use AAAA-MM-DD.', campos={'data': 'Data inválida.'})
    return dia


def serializar_registro(registro):
    return {
        'data': registro.data.isoformat(),
        'fluxo': registro.fluxo,
        'humor': registro.humor,
        'sintomas': [
            {'codigo': rs.sintoma.codigo, 'nome': rs.sintoma.nome, 'intensidade': rs.intensidade}
            for rs in registro.sintomas.all()
        ],
    }


def registros_com_sintomas(usuario):
    sintomas = Prefetch('sintomas', queryset=RegistroSintoma.objects.select_related('sintoma').order_by('sintoma__ordem'))
    return RegistroDiario.objects.filter(usuario=usuario).prefetch_related(sintomas)


def estado_da_situacao(usuario):
    return {
        'situacao': usuario.situacao_menstrual,
        'diario_disponivel': usuario.diario_disponivel,
        'consentimento_saude': usuario.consentimento_saude_ativo(),
        'opcoes': c.rotulos(c.SITUACOES_MENSTRUAIS),
    }


class DefinirSituacao:
    def __init__(self, usuario, dados):
        self.usuario = usuario
        self.situacao = dados.get('situacao') if isinstance(dados, dict) else None

    def executar(self):
        exigir_acesso(self.usuario, disponibilidade=False)
        if self.situacao not in c.codigos(c.SITUACOES_MENSTRUAIS):
            raise ErroDiario('Escolha uma das opções.', campos={'situacao': 'Escolha uma das opções.'})
        self.usuario.situacao_menstrual = self.situacao
        self.usuario.save(update_fields=['situacao_menstrual'])
        return estado_da_situacao(self.usuario)


class ConsultarMes:
    def __init__(self, usuario, mes=None):
        self.usuario = usuario
        self.mes = (mes or '').strip()

    def executar(self):
        exigir_acesso(self.usuario)
        atual = hoje()
        if self.mes:
            achado = FORMATO_MES.match(self.mes)
            if not achado or not 1 <= int(achado.group(2)) <= 12:
                raise ErroDiario('Mês inválido. Use AAAA-MM.', campos={'mes': 'Mês inválido.'})
            ano, mes = int(achado.group(1)), int(achado.group(2))
        else:
            ano, mes = atual.year, atual.month
        if (ano, mes) > (atual.year, atual.month):
            raise ErroDiario('Ainda não dá para ver registros de um mês que não chegou.', campos={'mes': 'Mês futuro.'})
        inicio = date(ano, mes, 1)
        fim = date(ano + (mes == 12), mes % 12 + 1, 1)
        registros = registros_com_sintomas(self.usuario).filter(data__gte=inicio, data__lt=fim)
        return {
            'mes': f'{ano:04d}-{mes:02d}',
            'registros': [serializar_registro(r) for r in registros],
            'sintomas': [{'codigo': s.codigo, 'nome': s.nome} for s in Sintoma.objects.filter(ativo=True)],
            'opcoes': {
                'fluxo': c.rotulos(c.FLUXOS),
                'humor': c.rotulos(c.HUMORES),
                'intensidade': c.rotulos(c.INTENSIDADES),
            },
        }


class RegistrarDia:
    def __init__(self, usuario, dia, dados):
        self.usuario = usuario
        self.dia = dia
        self.dados = dados

    def executar(self):
        exigir_acesso(self.usuario)
        dia = ler_dia(self.dia)
        if dia > hoje():
            raise ErroDiario('Não dá para registrar um dia que ainda não chegou.', campos={'data': 'Data futura.'})
        if not isinstance(self.dados, dict):
            raise ErroDiario('JSON inválido.')
        fluxo, humor, sintomas = self._validar()
        with transaction.atomic():
            registro, _ = RegistroDiario.objects.update_or_create(
                usuario=self.usuario, data=dia, defaults={'fluxo': fluxo, 'humor': humor},
            )
            RegistroSintoma.objects.filter(registro=registro).delete()
            RegistroSintoma.objects.bulk_create(
                RegistroSintoma(registro=registro, sintoma=sintoma, intensidade=intensidade)
                for sintoma, intensidade in sintomas
            )
        return serializar_registro(registros_com_sintomas(self.usuario).get(pk=registro.pk))

    def _validar(self):
        campos = {}
        for chave in set(self.dados) - CAMPOS_ACEITOS:
            campos[chave] = 'Este campo não é aceito no diário.'
        fluxo = self.dados.get('fluxo')
        if fluxo is not None and fluxo not in c.codigos(c.FLUXOS):
            campos['fluxo'] = 'Escolha uma das opções de menstruação.'
        humor = self.dados.get('humor')
        if humor is not None and humor not in c.codigos(c.HUMORES):
            campos['humor'] = 'Escolha uma das opções de humor.'
        sintomas = self._sintomas(campos)
        if not campos and fluxo is None and humor is None and not sintomas:
            campos['registro'] = 'Escolha pelo menos a menstruação, o humor ou um sintoma.'
        if campos:
            raise ErroDiario('Revise os campos destacados.', campos=campos)
        return fluxo, humor, sintomas

    def _sintomas(self, campos):
        lista = self.dados.get('sintomas')
        if lista is None:
            return []
        if not isinstance(lista, list):
            campos['sintomas'] = 'Envie os sintomas em uma lista.'
            return []
        ativos = {s.codigo: s for s in Sintoma.objects.filter(ativo=True)}
        escolhidos = []
        vistos = set()
        for i, item in enumerate(lista):
            codigo = item.get('codigo') if isinstance(item, dict) else None
            intensidade = item.get('intensidade') if isinstance(item, dict) else None
            if codigo not in ativos:
                campos[f'sintomas.{i}.codigo'] = 'Sintoma desconhecido ou indisponível.'
                continue
            if codigo in vistos:
                campos[f'sintomas.{i}.codigo'] = 'Este sintoma já foi informado.'
                continue
            if intensidade not in c.INTENSIDADES_GRAVADAS:
                campos[f'sintomas.{i}.intensidade'] = 'Escolha leve, médio ou intenso.'
                continue
            vistos.add(codigo)
            escolhidos.append((ativos[codigo], intensidade))
        return escolhidos


class ExcluirDia:
    def __init__(self, usuario, dia):
        self.usuario = usuario
        self.dia = dia

    def executar(self):
        dia = ler_dia(self.dia)
        return RegistroDiario.objects.filter(usuario=self.usuario, data=dia).delete()[0] > 0


class ApagarDiario:
    def __init__(self, usuario, dados):
        self.usuario = usuario
        self.confirmar = isinstance(dados, dict) and dados.get('confirmar') is True

    def executar(self):
        if not self.confirmar:
            raise ErroDiario('Confirme para apagar todo o diário.', campos={'confirmar': 'Envie confirmar: true.'})
        return apagar_diario(self.usuario)


def apagar_diario(usuario):
    with transaction.atomic():
        quantidade = RegistroDiario.objects.filter(usuario=usuario).count()
        RegistroSintoma.objects.filter(registro__usuario=usuario).delete()
        RegistroDiario.objects.filter(usuario=usuario).delete()
    return quantidade


def mais_frequente(valores):
    if not valores:
        return None
    contagem = Counter(v for v, _ in valores)
    maximo = max(contagem.values())
    empatados = {v for v, n in contagem.items() if n == maximo}
    return max((d, v) for v, d in valores if v in empatados)[1]


class ResumoCiclo:
    def __init__(self, usuario, referencia=None):
        self.usuario = usuario
        self.referencia = referencia

    def executar(self):
        exigir_acesso(self.usuario)
        referencia = self.referencia or hoje()
        registros = list(registros_com_sintomas(self.usuario).filter(data__lte=referencia).order_by('data'))
        inicios = self._inicios(registros)
        duracoes = [(b - a).days for a, b in zip(inicios, inicios[1:])]
        validas = [d for d in duracoes if c.CICLO_MINIMO_DIAS <= d <= c.CICLO_MAXIMO_DIAS]
        descartados = len(duracoes) - len(validas)
        consideradas = validas[-c.CICLOS_NA_MEDIA:]
        disponivel = len(validas) >= c.CICLOS_VALIDOS_MINIMOS
        media = int(sum(consideradas) / len(consideradas) + 0.5) if disponivel else None

        proxima = inicios[-1] + timedelta(days=media) if disponivel else None
        dia_do_ciclo = None
        if disponivel and (referencia - inicios[-1]).days <= c.CICLO_MAXIMO_DIAS:
            dia_do_ciclo = (referencia - inicios[-1]).days + 1
        return {
            'duracao': {
                'status': 'ok' if disponivel else 'aprendendo',
                'media_dias': media,
                'ciclos_considerados': len(consideradas) if disponivel else 0,
                'ciclos_descartados': descartados,
            },
            'ultimo_inicio': inicios[-1].isoformat() if inicios else None,
            'proxima_data': proxima.isoformat() if proxima else None,
            'atrasada': bool(proxima and proxima < referencia),
            'dia_do_ciclo': dia_do_ciclo,
            'fluxo_mais_frequente': self._fluxo(registros),
            'humor_mais_frequente': self._humor(registros),
            'sintomas_mais_frequentes': self._sintomas(registros),
            'aviso': c.AVISO_RESUMO,
            'orientacao': c.ORIENTACAO_CICLOS_DESCARTADOS if descartados else None,
        }

    @staticmethod
    def _inicios(registros):
        com_fluxo = [r.data for r in registros if r.fluxo in c.FLUXOS_COM_MENSTRUACAO]
        datas = set(com_fluxo)
        return [
            d for d in com_fluxo
            if not any(d - timedelta(days=n) in datas for n in range(1, c.JANELA_INICIO_DIAS + 1))
        ]

    @staticmethod
    def _fluxo(registros):
        valores = [(r.fluxo, r.data) for r in registros if r.fluxo in c.FLUXOS_COM_MENSTRUACAO]
        return mais_frequente(valores) if len(valores) >= c.REGISTROS_MINIMOS_TENDENCIA else None

    @staticmethod
    def _humor(registros):
        valores = [(r.humor, r.data) for r in registros if r.humor]
        return mais_frequente(valores) if len(valores) >= c.REGISTROS_MINIMOS_TENDENCIA else None

    @staticmethod
    def _sintomas(registros):
        por_sintoma = {}
        for r in registros:
            for rs in r.sintomas.all():
                por_sintoma.setdefault(rs.sintoma, []).append((rs.intensidade, r.data))
        candidatos = [
            (len(valores), max(d for _, d in valores), sintoma, valores)
            for sintoma, valores in por_sintoma.items() if len(valores) >= c.REGISTROS_MINIMOS_TENDENCIA
        ]
        candidatos.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [
            {'codigo': sintoma.codigo, 'nome': sintoma.nome, 'dias': dias, 'intensidade': mais_frequente(valores)}
            for dias, _, sintoma, valores in candidatos[:c.SINTOMAS_NA_TENDENCIA]
        ]
