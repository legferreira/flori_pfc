from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.db import models
from django.test import TestCase
from django.utils import timezone

from users.models import Consentimento, LogAtividade, Token, Usuario
from users.services import ExcluirConta

from . import constantes
from .models import RegistroDiario, RegistroSintoma, Sintoma
from .services import ResumoCiclo


def criar_usuario(email, perfil=Usuario.Perfil.USER):
    usuario = Usuario(
        nome='Ana', sobrenome='Souza', apelido=email.split('@')[0], data_nascimento='10/04/2008', email=email,
        perfil=perfil,
    )
    usuario.definir_senha('senha-12345')
    usuario.save()
    for tipo in Consentimento.DOCUMENTOS:
        Consentimento.objects.create(usuario=usuario, tipo=tipo, versao_documento='2.0', aceito=True)
    return usuario


class BaseDiarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('carregar_sintomas', stdout=StringIO())

    def setUp(self):
        self.usuario = criar_usuario('ana@exemplo.com')
        self.auth = self.cabecalho(self.usuario)
        self.aceitar_saude(self.usuario)
        self.usuario.situacao_menstrual = 'ja_menstruo'
        self.usuario.save()
        self.hoje = timezone.localdate()

    def cabecalho(self, usuario):
        return {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=usuario).chave}'}

    def aceitar_saude(self, usuario, aceito=True):
        Consentimento.objects.create(
            usuario=usuario, tipo=Consentimento.Tipo.SAUDE, versao_documento='1.0', aceito=aceito,
        )

    def chamar(self, metodo, url, dados=None, auth=None):
        extra = self.auth if auth is None else auth
        return getattr(self.client, metodo)(url, dados if dados is not None else {}, content_type='application/json', **extra)

    def registrar(self, dia, auth=None, **dados):
        return self.chamar('put', f'/api/diario/{dia}', dados, auth=auth)

    def rotas(self):
        dia = self.hoje.isoformat()
        return [
            ('get', '/api/diario', None), ('get', '/api/diario/resumo', None),
            ('put', f'/api/diario/{dia}', {'fluxo': 'leve'}), ('put', '/api/diario/situacao', {'situacao': 'ja_menstruo'}),
        ]


class CarregarSintomasTests(BaseDiarioTests):
    def test_idempotente_e_nao_sobrescreve(self):
        self.assertEqual(Sintoma.objects.count(), 8)
        Sintoma.objects.filter(codigo='acne').update(nome='Espinhas')
        call_command('carregar_sintomas', stdout=StringIO())
        self.assertEqual(Sintoma.objects.count(), 8)
        self.assertEqual(Sintoma.objects.get(codigo='acne').nome, 'Espinhas')
        self.assertEqual(list(Sintoma.objects.values_list('codigo', flat=True))[:2], ['colica', 'dor_de_cabeca'])


class ConsentimentoESituacaoTests(BaseDiarioTests):
    def test_sem_consentimento_saude_tudo_bloqueado_menos_ler_a_situacao(self):
        outra = criar_usuario('bia@exemplo.com')
        auth = self.cabecalho(outra)
        for metodo, url, dados in self.rotas():
            resposta = self.chamar(metodo, url, dados, auth=auth)
            self.assertEqual(resposta.status_code, 403, url)
            self.assertEqual(resposta.json()['codigo'], 'consentimento_saude_necessario', url)
        situacao = self.chamar('get', '/api/diario/situacao', auth=auth).json()
        self.assertEqual((situacao['situacao'], situacao['diario_disponivel'], situacao['consentimento_saude']), (None, False, False))

    def test_consentimento_saude_pelas_rotas_existentes(self):
        outra = criar_usuario('bia@exemplo.com')
        auth = self.cabecalho(outra)
        perfil = self.chamar('post', '/api/perfil/consentimentos', {'tipo': 'saude', 'aceito': True}, auth=auth).json()
        self.assertEqual(perfil['consentimento_saude']['aceito'], True)
        self.assertEqual(perfil['consentimento_saude']['versao_documento'], '1.0')
        self.assertNotIn('saude', [c['tipo'] for c in perfil['consentimentos']])
        registro = Consentimento.objects.get(usuario=outra, tipo='saude')
        self.assertEqual(registro.ip_origem, '127.0.0.1')
        self.chamar('post', '/api/perfil/consentimentos', {'tipo': 'saude', 'aceito': False}, auth=auth)
        self.assertEqual(Consentimento.objects.filter(usuario=outra, tipo='saude').count(), 2)
        self.assertFalse(Usuario.objects.get(pk=outra.pk).consentimento_saude_ativo())
        self.assertNotEqual(self.chamar('get', '/api/trilha', auth=auth).status_code, 403)
        self.assertEqual(self.chamar('get', '/api/perfil', auth=auth).json()['consentimento_saude']['aceito'], False)

    def test_situacao_exige_consentimento_e_controla_o_diario(self):
        self.assertEqual(self.chamar('put', '/api/diario/situacao', {'situacao': 'outra'}).status_code, 400)
        self.registrar(self.hoje.isoformat(), fluxo='leve')
        for situacao, disponivel in (('ainda_nao', False), ('nao_tenho_certeza', True), ('ja_menstruo', True)):
            corpo = self.chamar('put', '/api/diario/situacao', {'situacao': situacao}).json()
            self.assertEqual(corpo['diario_disponivel'], disponivel, situacao)
            resposta = self.chamar('get', '/api/diario')
            self.assertEqual(resposta.status_code, 200 if disponivel else 403, situacao)
            if not disponivel:
                self.assertEqual(resposta.json()['codigo'], 'diario_indisponivel')
                self.assertEqual(self.chamar('get', '/api/diario/resumo').json()['codigo'], 'diario_indisponivel')
                self.assertEqual(self.registrar(self.hoje.isoformat(), fluxo='leve').status_code, 403)
            self.assertEqual(RegistroDiario.objects.filter(usuario=self.usuario).count(), 1)
        self.chamar('put', '/api/diario/situacao', {'situacao': 'ainda_nao'})
        self.assertEqual(self.chamar('delete', f'/api/diario/{self.hoje.isoformat()}').status_code, 204)

    def test_situacao_nula_esconde_o_diario(self):
        Usuario.objects.filter(pk=self.usuario.pk).update(situacao_menstrual=None)
        self.assertEqual(self.chamar('get', '/api/diario').json()['codigo'], 'diario_indisponivel')
        self.assertFalse(self.chamar('get', '/api/perfil').json()['diario_disponivel'])

    def test_sem_diario_disponivel_as_apis_continuam_bloqueadas(self):
        for situacao in (None, 'ainda_nao'):
            Usuario.objects.filter(pk=self.usuario.pk).update(situacao_menstrual=situacao)
            perfil = self.chamar('get', '/api/perfil').json()
            self.assertEqual((perfil['perfil'], perfil['diario_disponivel']), ('user', False), situacao)
            for resposta in (
                self.chamar('get', '/api/diario'),
                self.chamar('get', '/api/diario/resumo'),
                self.registrar(self.hoje.isoformat(), fluxo='leve'),
            ):
                self.assertEqual(resposta.status_code, 403, situacao)
                self.assertEqual(resposta.json()['codigo'], 'diario_indisponivel', situacao)
            situacao_atual = self.chamar('get', '/api/diario/situacao').json()
            self.assertEqual((situacao_atual['situacao'], situacao_atual['diario_disponivel']), (situacao, False))
        self.assertFalse(RegistroDiario.objects.filter(usuario=self.usuario).exists())

    def test_revogado_bloqueia_mas_preserva_e_permite_excluir(self):
        self.registrar(self.hoje.isoformat(), fluxo='leve')
        self.registrar((self.hoje - timedelta(days=1)).isoformat(), humor='normal')
        self.aceitar_saude(self.usuario, aceito=False)
        for metodo, url, dados in self.rotas():
            resposta = self.chamar(metodo, url, dados)
            self.assertEqual((resposta.status_code, resposta.json()['codigo']), (403, 'consentimento_saude_necessario'), url)
        self.assertEqual(RegistroDiario.objects.filter(usuario=self.usuario).count(), 2)
        self.assertEqual(self.chamar('delete', f'/api/diario/{self.hoje.isoformat()}').status_code, 204)
        self.assertEqual(self.chamar('delete', '/api/diario', {'confirmar': True}).json(), {'apagados': 1})
        self.assertFalse(RegistroDiario.objects.filter(usuario=self.usuario).exists())


class RegistroTests(BaseDiarioTests):
    def test_um_registro_por_dia_e_substituicao_inteira(self):
        dia = self.hoje.isoformat()
        primeiro = self.registrar(dia, fluxo='medio', humor='triste', sintomas=[
            {'codigo': 'colica', 'intensidade': 'intenso'}, {'codigo': 'acne', 'intensidade': 'leve'},
        ])
        self.assertEqual(primeiro.status_code, 200, primeiro.content)
        segundo = self.registrar(dia, humor='normal', sintomas=[{'codigo': 'acne', 'intensidade': 'medio'}]).json()
        self.assertEqual(RegistroDiario.objects.filter(usuario=self.usuario).count(), 1)
        self.assertEqual((segundo['fluxo'], segundo['humor']), (None, 'normal'))
        self.assertEqual([(s['codigo'], s['intensidade']) for s in segundo['sintomas']], [('acne', 'medio')])
        self.assertEqual(RegistroSintoma.objects.count(), 1)
        self.registrar(dia, fluxo='sem_fluxo')
        self.assertFalse(RegistroSintoma.objects.exists())

    def test_data_futura_recusada_e_hoje_permitido(self):
        amanha = (self.hoje + timedelta(days=1)).isoformat()
        resposta = self.registrar(amanha, fluxo='leve')
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('data', resposta.json()['campos'])
        self.assertEqual(self.registrar(self.hoje.isoformat(), fluxo='leve').status_code, 200)
        self.assertEqual(self.registrar('2026-02-30', fluxo='leve').status_code, 400)
        with patch('diario.services.hoje', return_value=date(2026, 3, 10)):
            self.assertEqual(self.registrar('2026-03-10', fluxo='leve').status_code, 200)
            self.assertEqual(self.registrar('2026-03-11', fluxo='leve').status_code, 400)

    def test_listas_fixas_e_pelo_menos_um_campo(self):
        dia = self.hoje.isoformat()
        casos = [
            ({'fluxo': 'muito'}, 'fluxo'), ({'humor': 'feliz'}, 'humor'), ({}, 'registro'),
            ({'fluxo': None, 'humor': None, 'sintomas': []}, 'registro'),
            ({'sintomas': [{'codigo': 'febre', 'intensidade': 'leve'}]}, 'sintomas.0.codigo'),
            ({'sintomas': [{'codigo': 'acne', 'intensidade': 'nenhum'}]}, 'sintomas.0.intensidade'),
            ({'sintomas': [{'codigo': 'acne', 'intensidade': 'forte'}]}, 'sintomas.0.intensidade'),
            ({'sintomas': [{'codigo': 'acne', 'intensidade': 'leve'}, {'codigo': 'acne', 'intensidade': 'medio'}]}, 'sintomas.1.codigo'),
            ({'sintomas': 'colica'}, 'sintomas'),
            ({'fluxo': 'leve', 'nota': 'senti dor'}, 'nota'),
        ]
        for dados, campo in casos:
            resposta = self.registrar(dia, **dados)
            self.assertEqual(resposta.status_code, 400, dados)
            self.assertIn(campo, resposta.json()['campos'], dados)
        Sintoma.objects.filter(codigo='nausea').update(ativo=False)
        resposta = self.registrar(dia, sintomas=[{'codigo': 'nausea', 'intensidade': 'leve'}])
        self.assertIn('sintomas.0.codigo', resposta.json()['campos'])
        self.assertFalse(RegistroDiario.objects.exists())
        self.assertEqual(self.registrar(dia, sintomas=[{'codigo': 'colica', 'intensidade': 'leve'}]).status_code, 200)

    def test_nenhum_campo_de_texto_livre(self):
        for modelo in (RegistroDiario, RegistroSintoma):
            for campo in modelo._meta.concrete_fields:
                self.assertNotIsInstance(campo, models.TextField, campo.name)
        livres = {f.name for f in RegistroDiario._meta.concrete_fields if isinstance(f, models.CharField)}
        self.assertEqual(livres, {'fluxo', 'humor'})

    def test_consulta_do_mes(self):
        self.registrar(self.hoje.isoformat(), fluxo='leve', sintomas=[{'codigo': 'colica', 'intensidade': 'leve'}])
        corpo = self.chamar('get', f'/api/diario?mes={self.hoje:%Y-%m}').json()
        self.assertEqual(corpo['registros'][0]['sintomas'][0]['codigo'], 'colica')
        self.assertEqual(len(corpo['sintomas']), 8)
        self.assertEqual([o['rotulo'] for o in corpo['opcoes']['fluxo']], ['Não', 'Leve', 'Médio', 'Intenso'])
        self.assertEqual([o['rotulo'] for o in corpo['opcoes']['humor']], ['Triste', 'Cansada', 'Normal', 'Animada'])
        self.assertEqual([o['rotulo'] for o in corpo['opcoes']['intensidade']], ['Nenhum', 'Leve', 'Médio', 'Intenso'])
        proximo = (self.hoje.replace(day=1) + timedelta(days=32)).strftime('%Y-%m')
        self.assertEqual(self.chamar('get', f'/api/diario?mes={proximo}').status_code, 400)
        for invalido in ('2026-13', '2026/01', 'janeiro'):
            self.assertEqual(self.chamar('get', f'/api/diario?mes={invalido}').status_code, 400, invalido)
        self.assertEqual(self.chamar('get', '/api/diario?mes=2020-01').json()['registros'], [])

    def test_apagar_tudo_exige_confirmar(self):
        self.registrar(self.hoje.isoformat(), fluxo='leve')
        self.assertEqual(self.chamar('delete', '/api/diario', {}).status_code, 400)
        self.assertEqual(self.chamar('delete', '/api/diario', {'confirmar': 'sim'}).status_code, 400)
        self.assertTrue(RegistroDiario.objects.exists())
        self.assertEqual(self.chamar('delete', '/api/diario', {'confirmar': True}).status_code, 200)
        self.assertFalse(RegistroDiario.objects.exists())

    def test_diario_nao_gera_log(self):
        antes = LogAtividade.objects.count()
        dia = self.hoje.isoformat()
        self.registrar(dia, fluxo='leve')
        self.chamar('get', '/api/diario')
        self.chamar('get', '/api/diario/resumo')
        self.chamar('delete', f'/api/diario/{dia}')
        self.chamar('put', '/api/diario/situacao', {'situacao': 'nao_tenho_certeza'})
        self.chamar('delete', '/api/diario', {'confirmar': True})
        self.assertEqual(LogAtividade.objects.count(), antes)


class IsolamentoEAdminTests(BaseDiarioTests):
    def test_user_a_nao_le_nem_altera_user_b(self):
        dia = self.hoje.isoformat()
        self.registrar(dia, fluxo='intenso')
        bia = criar_usuario('bia@exemplo.com')
        self.aceitar_saude(bia)
        Usuario.objects.filter(pk=bia.pk).update(situacao_menstrual='ja_menstruo')
        auth_bia = self.cabecalho(bia)
        self.assertEqual(self.chamar('get', '/api/diario', auth=auth_bia).json()['registros'], [])
        self.assertEqual(self.chamar('get', '/api/diario/resumo', auth=auth_bia).json()['fluxo_mais_frequente'], None)
        self.registrar(dia, auth=auth_bia, humor='animada')
        self.chamar('delete', f'/api/diario/{dia}', auth=auth_bia)
        self.chamar('delete', '/api/diario', {'confirmar': True}, auth=auth_bia)
        registro = RegistroDiario.objects.get(usuario=self.usuario)
        self.assertEqual((registro.fluxo, registro.humor), ('intenso', None))

    def test_admin_recebe_403_em_tudo(self):
        admin = criar_usuario('admin@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        auth = self.cabecalho(admin)
        rotas = self.rotas() + [
            ('get', '/api/diario/situacao', None), ('delete', '/api/diario', {'confirmar': True}),
            ('delete', f'/api/diario/{self.hoje.isoformat()}', None),
        ]
        for metodo, url, dados in rotas:
            resposta = self.chamar(metodo, url, dados, auth=auth)
            self.assertEqual(resposta.status_code, 403, f'{metodo} {url}')
        resposta = self.chamar('post', '/api/perfil/consentimentos', {'tipo': 'saude', 'aceito': True}, auth=auth)
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(Consentimento.objects.filter(usuario=admin, tipo='saude').exists())
        self.assertFalse(Usuario.objects.get(pk=admin.pk).diario_disponivel)

    def test_endpoints_admin_nao_expoem_diario(self):
        self.registrar(self.hoje.isoformat(), fluxo='intenso', humor='triste', sintomas=[{'codigo': 'colica', 'intensidade': 'leve'}])
        admin = criar_usuario('admin@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        auth = self.cabecalho(admin)
        for url in ('/api/admin/dashboard', '/api/admin/users', '/api/admin/users?situacao=todas'):
            texto = self.chamar('get', url, auth=auth).content.decode()
            for proibido in ('fluxo', 'humor', 'situacao_menstrual', 'ja_menstruo', 'intenso', 'Cólica', 'colica', 'diario'):
                self.assertNotIn(proibido, texto, f'{url} {proibido}')

    def test_exclusao_de_conta_apaga_diario_sintomas_e_situacao(self):
        self.registrar(self.hoje.isoformat(), fluxo='leve', sintomas=[{'codigo': 'colica', 'intensidade': 'leve'}])
        ExcluirConta(self.usuario.id).executar()
        conta = Usuario.objects.get(pk=self.usuario.pk)
        self.assertIsNone(conta.situacao_menstrual)
        self.assertFalse(RegistroDiario.objects.exists())
        self.assertFalse(RegistroSintoma.objects.exists())

    def test_exportacao_inclui_o_proprio_diario(self):
        self.registrar(self.hoje.isoformat(), humor='normal')
        corpo = self.chamar('get', '/api/perfil/exportacao').json()
        self.assertEqual(corpo['situacao_menstrual'], 'ja_menstruo')
        self.assertEqual(corpo['diario'][0]['humor'], 'normal')


class ResumoTests(BaseDiarioTests):
    def marcar(self, dia, fluxo=None, humor=None, sintomas=()):
        registro = RegistroDiario.objects.create(usuario=self.usuario, data=dia, fluxo=fluxo, humor=humor)
        for codigo, intensidade in sintomas:
            RegistroSintoma.objects.create(registro=registro, sintoma=Sintoma.objects.get(codigo=codigo), intensidade=intensidade)

    def resumo(self, referencia):
        return ResumoCiclo(self.usuario, referencia=referencia).executar()

    def test_exemplo_do_enunciado(self):
        for inicio in (date(2026, 1, 1), date(2026, 1, 29), date(2026, 2, 28)):
            self.marcar(inicio, fluxo='medio')
            self.marcar(inicio + timedelta(days=1), fluxo='leve')
            self.marcar(inicio + timedelta(days=3), fluxo='leve')
        resumo = self.resumo(date(2026, 3, 10))
        self.assertEqual(resumo['duracao'], {'status': 'ok', 'media_dias': 29, 'ciclos_considerados': 2, 'ciclos_descartados': 0})
        self.assertEqual((resumo['proxima_data'], resumo['atrasada'], resumo['dia_do_ciclo']), ('2026-03-29', False, 11))
        self.assertEqual(resumo['aviso'], constantes.AVISO_RESUMO)
        self.assertIsNone(resumo['orientacao'])
        atrasado = self.resumo(date(2026, 4, 5))
        self.assertEqual((atrasado['atrasada'], atrasado['dia_do_ciclo']), (True, 37))
        self.assertIsNone(self.resumo(date(2026, 4, 20))['dia_do_ciclo'])

    def test_pela_api(self):
        for inicio in (date(2026, 1, 1), date(2026, 1, 29), date(2026, 2, 28)):
            self.marcar(inicio, fluxo='intenso')
        with patch('diario.services.hoje', return_value=date(2026, 3, 10)):
            corpo = self.chamar('get', '/api/diario/resumo').json()
        self.assertEqual((corpo['proxima_data'], corpo['dia_do_ciclo'], corpo['duracao']['media_dias']), ('2026-03-29', 11, 29))

    def test_ciclo_fora_da_faixa_descartado_com_orientacao(self):
        for inicio in (date(2026, 1, 1), date(2026, 1, 29), date(2026, 2, 12), date(2026, 3, 14)):
            self.marcar(inicio, fluxo='medio')
        resumo = self.resumo(date(2026, 3, 20))
        self.assertEqual(resumo['duracao'], {'status': 'ok', 'media_dias': 29, 'ciclos_considerados': 2, 'ciclos_descartados': 1})
        self.assertEqual(resumo['orientacao'], constantes.ORIENTACAO_CICLOS_DESCARTADOS)
        self.marcar(date(2026, 6, 1), fluxo='medio')
        self.assertEqual(self.resumo(date(2026, 6, 2))['duracao']['ciclos_descartados'], 2)

    def test_menos_de_dois_ciclos_validos_esta_aprendendo(self):
        vazio = self.resumo(date(2026, 3, 10))
        self.assertEqual(vazio['duracao']['status'], 'aprendendo')
        self.assertEqual((vazio['proxima_data'], vazio['dia_do_ciclo'], vazio['atrasada']), (None, None, False))
        self.assertEqual(
            (vazio['fluxo_mais_frequente'], vazio['humor_mais_frequente'], vazio['sintomas_mais_frequentes']), (None, None, []),
        )
        self.marcar(date(2026, 1, 1), fluxo='leve')
        self.marcar(date(2026, 1, 29), fluxo='leve')
        resumo = self.resumo(date(2026, 2, 5))
        self.assertEqual((resumo['duracao']['status'], resumo['duracao']['media_dias'], resumo['proxima_data']), ('aprendendo', None, None))

    def test_janela_de_7_dias_para_o_inicio(self):
        self.marcar(date(2026, 1, 1), fluxo='leve')
        self.marcar(date(2026, 1, 8), fluxo='leve')
        self.marcar(date(2026, 1, 30), fluxo='leve')
        self.marcar(date(2026, 2, 6), fluxo='leve')
        self.marcar(date(2026, 2, 28), fluxo='leve')
        self.marcar(date(2026, 3, 5), fluxo='sem_fluxo')
        resumo = self.resumo(date(2026, 3, 10))
        self.assertEqual(resumo['ultimo_inicio'], '2026-02-28')
        self.assertEqual(resumo['duracao']['media_dias'], 29)
        self.assertEqual(resumo['duracao']['ciclos_considerados'], 2)

    def test_usa_so_os_6_ultimos_ciclos_validos(self):
        inicio = date(2025, 1, 1)
        datas = [inicio]
        for duracao in (40, 40, 28, 28, 28, 28, 28, 28):
            datas.append(datas[-1] + timedelta(days=duracao))
        for dia in datas:
            self.marcar(dia, fluxo='medio')
        resumo = self.resumo(datas[-1] + timedelta(days=2))
        self.assertEqual((resumo['duracao']['media_dias'], resumo['duracao']['ciclos_considerados']), (28, 6))

    def test_modas_de_fluxo_e_humor(self):
        for n in range(4):
            self.marcar(date(2026, 1, 1 + n), fluxo='sem_fluxo', humor='normal')
        self.marcar(date(2026, 1, 10), fluxo='leve', humor='triste')
        self.marcar(date(2026, 1, 11), fluxo='leve', humor='triste')
        self.marcar(date(2026, 1, 12), fluxo='medio')
        resumo = self.resumo(date(2026, 1, 20))
        self.assertEqual((resumo['fluxo_mais_frequente'], resumo['humor_mais_frequente']), ('leve', 'normal'))

    def test_empate_vale_o_mais_recente(self):
        self.marcar(date(2026, 1, 1), fluxo='leve', humor='animada')
        self.marcar(date(2026, 1, 2), fluxo='intenso', humor='triste')
        self.marcar(date(2026, 1, 3), fluxo='leve', humor='animada')
        self.marcar(date(2026, 1, 4), fluxo='intenso', humor='triste')
        resumo = self.resumo(date(2026, 1, 5))
        self.assertEqual((resumo['fluxo_mais_frequente'], resumo['humor_mais_frequente']), ('intenso', 'triste'))

    def test_tendencia_omitida_com_menos_de_3_registros(self):
        self.marcar(date(2026, 1, 1), fluxo='leve', humor='normal', sintomas=[('colica', 'leve')])
        self.marcar(date(2026, 1, 2), fluxo='leve', humor='normal', sintomas=[('colica', 'leve')])
        self.marcar(date(2026, 1, 3), fluxo='sem_fluxo')
        resumo = self.resumo(date(2026, 1, 5))
        self.assertEqual(
            (resumo['fluxo_mais_frequente'], resumo['humor_mais_frequente'], resumo['sintomas_mais_frequentes']), (None, None, []),
        )

    def test_top_3_sintomas_com_intensidade_mais_frequente(self):
        dias = [date(2026, 1, d) for d in range(1, 8)]
        planos = {
            'colica': ['leve', 'leve', 'intenso', 'leve', 'medio'],
            'dor_nas_costas': ['medio', 'medio', 'leve', 'leve'],
            'acne': ['leve', 'leve', 'leve', 'leve'],
            'inchaco': ['intenso', 'intenso', 'intenso'],
            'nausea': ['leve', 'leve'],
        }
        por_dia = {d: [] for d in dias}
        for codigo, intensidades in planos.items():
            for d, intensidade in zip(dias, intensidades):
                por_dia[d].append((codigo, intensidade))
        por_dia[dias[6]].append(('dor_nas_costas', 'leve'))
        for d, sintomas in por_dia.items():
            if sintomas:
                self.marcar(d, sintomas=sintomas)
        resumo = self.resumo(date(2026, 1, 10))
        self.assertEqual(
            [(s['codigo'], s['dias'], s['intensidade']) for s in resumo['sintomas_mais_frequentes']],
            [('dor_nas_costas', 5, 'leve'), ('colica', 5, 'leve'), ('acne', 4, 'leve')],
        )
