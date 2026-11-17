from datetime import date, datetime, timedelta

from django.utils import timezone

from trilha.models import Card, ProgressoCard, ProgressoTrilha, TentativaQuiz, Trilha
from users.models import Consentimento, LogAtividade, Usuario
from users.services import ExcluirConta

from .tests import BaseAdminTests, criar_usuario

URL = '/api/admin/dashboard'
DE, ATE = '2026-11-02', '2026-11-22'


def momento(ano, mes, dia, hora=12):
    return timezone.make_aware(datetime(ano, mes, dia, hora))


class BaseDashboardTests(BaseAdminTests):
    def setUp(self):
        super().setUp()
        Usuario.objects.filter(pk__in=[self.admin.pk, self.comum.pk]).update(criado_em=momento(2026, 1, 10))
        self.trilha = Trilha.objects.get()

    def painel(self, de=DE, ate=ATE):
        resposta = self.chamar('get', f'{URL}?de={de}&ate={ate}')
        self.assertEqual(resposta.status_code, 200, resposta.content)
        return resposta.json()

    def conta(self, email, criada=momento(2026, 1, 10)):
        usuario = criar_usuario(email)
        Usuario.objects.filter(pk=usuario.pk).update(criado_em=criada)
        return usuario

    def entrou(self, usuario, quando=momento(2026, 11, 10), acao=LogAtividade.Acao.LOGIN_SUCESSO):
        LogAtividade.objects.create(usuario=usuario, acao=acao, criado_em=quando)

    def concluir(self, usuario, codigos=None):
        cards = Card.objects.filter(codigo__in=codigos) if codigos else Card.objects.all()
        for card in cards:
            ProgressoCard.objects.create(usuario=usuario, card=card)
        if not codigos:
            ProgressoTrilha.objects.create(usuario=usuario, trilha=self.trilha, trilha_concluida_em=timezone.now())

    def tentativa(self, usuario, aprovada):
        TentativaQuiz.objects.create(
            usuario=usuario, trilha=self.trilha, total_perguntas=10, acertos=8 if aprovada else 4,
            percentual=80 if aprovada else 40, aprovada=aprovada, finalizada_em=timezone.now(),
        )


class PermissaoEPeriodoTests(BaseDashboardTests):
    def test_user_403_e_sem_token_401(self):
        self.assertEqual(self.chamar('get', URL, auth=self.auth_comum).status_code, 403)
        self.assertEqual(self.chamar('get', URL, auth={}).status_code, 401)

    def test_periodo_padrao_e_os_ultimos_30_dias_em_sao_paulo(self):
        corpo = self.chamar('get', URL).json()
        hoje = timezone.localdate()
        self.assertEqual(corpo['periodo'], {
            'de': (hoje - timedelta(days=29)).isoformat(), 'ate': hoje.isoformat(), 'dias': 30,
        })

    def test_validacao_do_intervalo(self):
        invertido = self.chamar('get', f'{URL}?de=2026-11-10&ate=2026-11-01')
        self.assertEqual(invertido.status_code, 400)
        self.assertIn('de', invertido.json()['campos'])
        longo = self.chamar('get', f'{URL}?de=2025-01-01&ate=2026-01-02')
        self.assertEqual(longo.status_code, 400)
        self.assertIn('ate', longo.json()['campos'])
        self.assertEqual(self.chamar('get', f'{URL}?de=2025-01-01&ate=2026-01-01').status_code, 200)
        formato = self.chamar('get', f'{URL}?de=10/11/2026&ate=2026-13-01')
        self.assertEqual(formato.status_code, 400)
        self.assertEqual(set(formato.json()['campos']), {'de', 'ate'})
        self.assertEqual(self.chamar('get', f'{URL}?de=2026-11-15&ate=2026-11-15').json()['periodo']['dias'], 1)

    def test_consulta_gera_log_com_o_periodo(self):
        self.painel()
        log = self.logs(LogAtividade.Acao.ADMIN_CONSULTOU_DASHBOARD).get()
        self.assertEqual(log.resumo, {'de': DE, 'ate': ATE})


class IndicadoresTests(BaseDashboardTests):
    def test_cadastros_no_periodo_com_limites_inclusivos(self):
        self.conta('a@exemplo.com', momento(2026, 11, 2, 0))
        self.conta('b@exemplo.com', momento(2026, 11, 22, 23))
        self.conta('fora@exemplo.com', momento(2026, 11, 23, 0))
        self.conta('antes@exemplo.com', momento(2026, 11, 1, 23))
        admin = criar_usuario('admin2@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        Usuario.objects.filter(pk=admin.pk).update(criado_em=momento(2026, 11, 10))
        self.assertEqual(self.painel()['cadastros_no_periodo'], 2)

    def test_entraram_e_contas_cadastradas(self):
        dentro = self.conta('dentro@exemplo.com')
        google = self.conta('google@exemplo.com')
        fora = self.conta('fora@exemplo.com')
        saiu = self.conta('saiu@exemplo.com')
        self.entrou(dentro)
        self.entrou(dentro, momento(2026, 11, 11))
        self.entrou(google, acao=LogAtividade.Acao.LOGIN_GOOGLE)
        self.entrou(fora, momento(2026, 10, 1))
        self.entrou(saiu)
        self.entrou(self.admin)
        LogAtividade.objects.create(usuario=fora, acao=LogAtividade.Acao.LOGIN_FALHA, criado_em=momento(2026, 11, 10))
        ExcluirConta(saiu.id).executar()
        corpo = self.painel()
        self.assertEqual(corpo['entraram_no_periodo'], 2)
        self.assertEqual(corpo['contas_cadastradas'], 4)

    def test_funil_aninhado(self):
        completa = self.conta('completa@exemplo.com')
        self.entrou(completa)
        self.concluir(completa)
        self.tentativa(completa, aprovada=False)
        self.tentativa(completa, aprovada=True)

        reprovada = self.conta('reprovada@exemplo.com')
        self.entrou(reprovada)
        self.concluir(reprovada)
        self.tentativa(reprovada, aprovada=False)

        estranha = self.conta('estranha@exemplo.com')
        self.entrou(estranha)
        self.tentativa(estranha, aprovada=True)

        meio = self.conta('meio@exemplo.com')
        self.entrou(meio)
        self.concluir(meio, ['1.1'])

        nao_entrou = self.conta('naoentrou@exemplo.com')
        self.concluir(nao_entrou)
        self.tentativa(nao_entrou, aprovada=True)

        self.entrou(self.comum)

        funil = self.painel()['funil']
        self.assertEqual(funil, {
            'entraram': 5, 'iniciaram_trilha': 3, 'concluiram_cards': 2, 'tentaram_quiz': 2, 'aprovadas_quiz': 1,
        })
        valores = list(funil.values())
        self.assertEqual(valores, sorted(valores, reverse=True))

    def test_avisos_do_periodo(self):
        saiu = self.conta('saiu@exemplo.com')
        ExcluirConta(saiu.id).executar()
        Usuario.objects.filter(pk=saiu.pk).update(excluido_em=momento(2026, 11, 5))
        antiga = self.conta('antiga@exemplo.com')
        ExcluirConta(antiga.id).executar()
        Usuario.objects.filter(pk=antiga.pk).update(excluido_em=momento(2026, 10, 5))
        revogado = Consentimento.objects.create(
            usuario=self.comum, tipo=Consentimento.Tipo.TERMOS_USO, versao_documento='2.0', aceito=False,
        )
        Consentimento.objects.filter(pk=revogado.pk).update(data_consentimento=momento(2026, 11, 6))
        fora = Consentimento.objects.create(
            usuario=self.comum, tipo=Consentimento.Tipo.POLITICA_PRIVACIDADE, versao_documento='2.0', aceito=False,
        )
        Consentimento.objects.filter(pk=fora.pk).update(data_consentimento=momento(2026, 12, 6))
        do_admin = Consentimento.objects.create(
            usuario=self.admin, tipo=Consentimento.Tipo.TERMOS_USO, versao_documento='2.0', aceito=False,
        )
        Consentimento.objects.filter(pk=do_admin.pk).update(data_consentimento=momento(2026, 11, 6))
        self.assertEqual(self.painel()['avisos_periodo'], {'contas_excluidas': 1, 'consentimentos_revogados': 1})


class GraficosTests(BaseDashboardTests):
    def test_situacao_das_contas_independe_do_periodo(self):
        concluiu = self.conta('concluiu@exemplo.com')
        self.concluir(concluiu)
        andamento = self.conta('andamento@exemplo.com')
        self.concluir(andamento, ['1.1', '1.2'])
        saiu = self.conta('saiu@exemplo.com')
        self.concluir(saiu)
        ExcluirConta(saiu.id).executar()
        situacao = self.painel('2020-01-01', '2020-01-31')['situacao_contas']
        self.assertEqual(situacao['total'], 3)
        self.assertEqual(situacao['grupos'], [
            {'chave': 'concluiram', 'contas': 1, 'percentual': 33.3},
            {'chave': 'em_andamento', 'contas': 1, 'percentual': 33.3},
            {'chave': 'nao_iniciaram', 'contas': 1, 'percentual': 33.3},
        ])

    def test_conclusao_por_card(self):
        primeira = self.conta('primeira@exemplo.com')
        self.concluir(primeira, ['1.1', '1.2'])
        segunda = self.conta('segunda@exemplo.com')
        self.concluir(segunda, ['1.1', '2.1'])
        self.concluir(self.admin, ['1.1', '1.2', '1.3'])
        Card.objects.filter(codigo='3.4').update(excluido_em=timezone.now())
        dados = self.painel()['conclusao_por_card']
        self.assertEqual(dados['base'], 2)
        self.assertEqual(len(dados['cards']), 11)
        self.assertEqual([c['numero'] for c in dados['cards']], list(range(1, 12)))
        primeiro, segundo, terceiro = dados['cards'][:3]
        self.assertEqual((primeiro['percentual'], segundo['percentual'], terceiro['percentual']), (100, 50, 0))
        self.assertEqual(primeiro['assunto'], 'Começando')
        self.assertEqual(dados['cards'][4]['assunto'], 'Entendendo o ciclo')
        self.assertEqual(dados['cards'][4]['percentual'], 50)

    def test_cadastros_por_semana_com_semana_vazia(self):
        self.conta('s1@exemplo.com', momento(2026, 11, 3))
        self.conta('s1b@exemplo.com', momento(2026, 11, 8, 23))
        self.conta('s3@exemplo.com', momento(2026, 11, 22, 20))
        semanas = self.painel()['cadastros_por_semana']
        self.assertEqual(
            [(s['rotulo'], s['cadastros']) for s in semanas], [('02/11', 2), ('09/11', 0), ('16/11', 1)],
        )

    def test_semana_comeca_na_segunda_mesmo_com_periodo_no_meio(self):
        self.conta('antes@exemplo.com', momento(2026, 11, 3))
        self.conta('dentro@exemplo.com', momento(2026, 11, 5))
        semanas = self.painel('2026-11-04', '2026-11-12')['cadastros_por_semana']
        self.assertEqual([(s['inicio'], s['cadastros']) for s in semanas], [('2026-11-02', 1), ('2026-11-09', 0)])
        self.assertEqual(date.fromisoformat(semanas[0]['inicio']).weekday(), 0)


class SemDadosIndividuaisTests(BaseDashboardTests):
    def test_resposta_sem_email_nem_apelido(self):
        alguem = self.conta('alguem.unico@exemplo.com')
        Usuario.objects.filter(pk=alguem.pk).update(apelido='ApelidoBemUnico')
        self.entrou(alguem)
        self.concluir(alguem)
        texto = self.chamar('get', f'{URL}?de={DE}&ate={ATE}').content.decode()
        for proibido in ('alguem.unico@exemplo.com', 'ApelidoBemUnico', 'comum@exemplo.com', str(alguem.id), '@'):
            self.assertNotIn(proibido, texto)
