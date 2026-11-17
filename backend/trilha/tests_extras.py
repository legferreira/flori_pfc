from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone

from administracao.tests import BaseAdminTests
from users.models import Token, Usuario

from .models import (
    AVISO_EXTRA, Assunto, Card, Certificado, FonteCard, Pergunta, ProgressoCard, ProgressoTrilha, TentativaQuiz,
)
from .tests import BaseTrilhaTests

ADMIN = '/api/admin/conteudo'


def ativar_extras():
    Assunto.objects.extras().update(ativo=True)
    Card.objects.extras().update(ativo=True)


class CargaDosExtrasTests(BaseTrilhaTests):
    def test_cria_tudo_desativado_com_fontes_e_e_idempotente(self):
        call_command('carregar_extras', stdout=StringIO())
        extras = Assunto.objects.extras()
        self.assertEqual(set(extras.values_list('codigo', flat=True)), {'extra_mudancas', 'extra_ajuda'})
        self.assertFalse(extras.filter(ativo=True).exists())
        cards = Card.objects.extras()
        self.assertEqual(cards.count(), 8)
        self.assertFalse(cards.filter(ativo=True).exists())
        self.assertTrue(all(FonteCard.objects.filter(card=c).count() == 3 for c in cards))
        self.assertEqual(sorted(extras.values_list('ordem', flat=True)), [1, 2])

        Card.objects.filter(codigo='EXM1').update(tema='Título editado pelo admin')
        Assunto.objects.filter(codigo='extra_ajuda').update(excluido_em=timezone.now())
        saida = StringIO()
        call_command('carregar_extras', stdout=saida)
        self.assertIn('Nada foi alterado', saida.getvalue())
        self.assertEqual(Card.objects.extras().count(), 8)
        self.assertEqual(Card.objects.get(codigo='EXM1').tema, 'Título editado pelo admin')
        self.assertIsNotNone(Assunto.objects.get(codigo='extra_ajuda').excluido_em)

    def test_carregar_trilha_continua_ignorando_extras(self):
        call_command('carregar_extras', stdout=StringIO())
        call_command('carregar_trilha', verbosity=0)
        self.assertEqual(Assunto.objects.oficiais().count(), 3)
        self.assertEqual(sorted(Assunto.objects.oficiais().values_list('ordem', flat=True)), [1, 2, 3])


class ExtrasDoUserTests(BaseTrilhaTests):
    def test_exige_login_e_vem_vazio_sem_extras_ativos(self):
        self.assertEqual(self.client.get('/api/trilha/extras').status_code, 401)
        self.assertEqual(self.get('/api/trilha/extras').json(), {'aviso': AVISO_EXTRA, 'assuntos': []})
        call_command('carregar_extras', stdout=StringIO())
        self.assertEqual(self.get('/api/trilha/extras').json()['assuntos'], [])

    def test_so_ativos_na_ordem_com_fontes_e_aviso(self):
        call_command('carregar_extras', stdout=StringIO())
        ativar_extras()
        Card.objects.filter(codigo='EXM2').update(ativo=False)
        Card.objects.filter(codigo='EXM3').update(excluido_em=timezone.now())
        corpo = self.get('/api/trilha/extras').json()
        self.assertEqual(corpo['aviso'], AVISO_EXTRA)
        self.assertEqual([a['titulo'] for a in corpo['assuntos']], ['Mudanças depois da primeira menstruação', 'Quando procurar ajuda'])
        mudancas = corpo['assuntos'][0]
        self.assertEqual([c['tema'] for c in mudancas['cards']], ['O corpo continua mudando', 'Ciclos irregulares no começo'])
        self.assertTrue(all(c['aviso'] == AVISO_EXTRA and len(c['fontes']) == 3 for c in mudancas['cards']))

    def test_assunto_extra_sem_card_visivel_fica_oculto(self):
        call_command('carregar_extras', stdout=StringIO())
        ativar_extras()
        Card.objects.filter(assunto__codigo='extra_ajuda').update(ativo=False)
        titulos = [a['titulo'] for a in self.get('/api/trilha/extras').json()['assuntos']]
        self.assertEqual(titulos, ['Mudanças depois da primeira menstruação'])
        Assunto.objects.filter(codigo='extra_mudancas').update(ativo=False)
        self.assertEqual(self.get('/api/trilha/extras').json()['assuntos'], [])

    def test_concluir_card_extra_e_recusado(self):
        call_command('carregar_extras', stdout=StringIO())
        ativar_extras()
        card = Card.objects.get(codigo='EXA1')
        resposta = self.post(f'/api/trilha/cards/{card.id}/concluir')
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(ProgressoCard.objects.filter(card=card).exists())

    def test_extras_fora_da_trilha_e_da_conclusao(self):
        call_command('carregar_extras', stdout=StringIO())
        ativar_extras()
        corpo = self.get('/api/trilha').json()
        self.assertEqual((len(corpo['assuntos']), corpo['total_cards']), (3, 12))
        self.concluir_todos(exceto=list(Card.objects.extras().values_list('codigo', flat=True)))
        corpo = self.get('/api/trilha').json()
        self.assertTrue(corpo['quiz']['liberado'])
        self.assertIsNotNone(ProgressoTrilha.objects.get(usuario=self.usuario).trilha_concluida_em)
        dashboard = self.get('/api/dashboard').json()
        self.assertEqual((dashboard['concluidos'], dashboard['total'], len(dashboard['assuntos'])), (12, 12, 3))

    def test_quiz_e_certificado_nao_mudam_ao_ativar_extras(self):
        self.concluir_todos()
        quiz = self.iniciar()
        resultado = self.enviar(quiz).json()
        codigo = resultado['certificado']['codigo']
        call_command('carregar_extras', stdout=StringIO())
        ativar_extras()
        trilha = self.get('/api/trilha').json()
        self.assertEqual(trilha['certificado']['codigo'], codigo)
        self.assertTrue(trilha['quiz']['liberado'])
        self.assertEqual(Certificado.objects.get().codigo, codigo)
        novo = self.iniciar()
        self.assertTrue(all(Pergunta.objects.get(pk=p['id']).assunto.tipo == 'oficial' for p in novo['perguntas']))
        reprovado = self.enviar(novo, erros=10).json()
        self.assertTrue(all(Assunto.objects.get(pk=a['id']).tipo == 'oficial' for a in reprovado['assuntos_a_revisar']))
        self.assertEqual(Certificado.objects.get().codigo, codigo)


class ExtrasNoAdminTests(BaseAdminTests):
    def novo_assunto(self, **dados):
        return self.chamar('post', f'{ADMIN}/assuntos', dados={'titulo': 'Extra novo', **dados})

    def test_criacao_com_tipo_e_ordem_independente(self):
        extra = self.novo_assunto(tipo='extra')
        self.assertEqual(extra.status_code, 201, extra.content)
        self.assertEqual((extra.json()['tipo'], extra.json()['ordem']), ('extra', 1))
        self.assertEqual(extra.json()['aviso'], AVISO_EXTRA)
        oficial = self.novo_assunto()
        self.assertEqual((oficial.json()['tipo'], oficial.json()['ordem']), ('oficial', 4))
        self.assertNotIn('aviso', oficial.json())
        self.assertEqual(self.novo_assunto(tipo='outro').status_code, 400)

    def test_tipo_nao_pode_ser_alterado(self):
        extra = self.novo_assunto(tipo='extra').json()
        resposta = self.chamar('put', f'{ADMIN}/assuntos/{extra["id"]}', dados={
            'titulo': 'Extra novo', 'tipo': 'oficial', 'atualizado_em': extra['atualizado_em'],
        })
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('tipo', resposta.json()['campos'])
        self.assertEqual(Assunto.objects.get(pk=extra['id']).tipo, 'extra')

    def test_filtro_de_tipo(self):
        call_command('carregar_extras', stdout=StringIO())
        tipos = lambda t: {a['tipo'] for a in self.chamar('get', f'{ADMIN}/assuntos?tipo={t}').json()['itens']}
        self.assertEqual(tipos('extra'), {'extra'})
        self.assertEqual(tipos('oficial'), {'oficial'})
        self.assertEqual(len(self.chamar('get', f'{ADMIN}/assuntos').json()['itens']), 5)
        self.assertEqual(self.chamar('get', f'{ADMIN}/assuntos?tipo=outro').status_code, 400)

    def test_impacto_e_visualizacao_do_extra(self):
        call_command('carregar_extras', stdout=StringIO())
        ativar_extras()
        assunto = Assunto.objects.get(codigo='extra_ajuda')
        impacto = self.chamar('get', f'{ADMIN}/assuntos/{assunto.id}/impacto').json()
        self.assertEqual(impacto, {'cards': 4, 'aviso': 'não afeta progresso nem certificados'})
        card = Card.objects.get(codigo='EXA1')
        self.assertEqual(self.chamar('get', f'{ADMIN}/cards/{card.id}/impacto').json()['aviso'], 'não afeta progresso nem certificados')
        visualizar = self.chamar('get', f'{ADMIN}/cards/{card.id}/visualizar').json()
        self.assertEqual((visualizar['aviso'], visualizar['card']['aviso']), (AVISO_EXTRA, AVISO_EXTRA))
        self.assertEqual(self.chamar('get', f'{ADMIN}/assuntos/{assunto.id}/visualizar').json()['aviso'], AVISO_EXTRA)

    def test_excluir_e_desativar_extra_nao_mexem_em_progresso(self):
        call_command('carregar_extras', stdout=StringIO())
        ativar_extras()
        for card in Card.objects.oficiais():
            ProgressoCard.objects.create(usuario=self.comum, card=card)
        antes = ProgressoCard.objects.count()
        assunto = Assunto.objects.get(codigo='extra_mudancas')
        self.chamar('post', f'{ADMIN}/assuntos/{assunto.id}/desativar')
        self.chamar('post', f'{ADMIN}/assuntos/{assunto.id}/excluir')
        self.assertEqual(ProgressoCard.objects.count(), antes)

    def test_pergunta_nao_aponta_para_assunto_extra(self):
        extra = Assunto.objects.get(pk=self.novo_assunto(tipo='extra').json()['id'])
        pergunta = Pergunta.objects.get(codigo='Q01')
        atual = self.chamar('get', f'{ADMIN}/perguntas/{pergunta.id}').json()
        dados = {'enunciado': atual['enunciado'], 'opcoes': atual['opcoes'], 'atualizado_em': atual['atualizado_em']}
        resposta = self.chamar('put', f'{ADMIN}/perguntas/{pergunta.id}', dados={**dados, 'assunto_id': str(extra.id)})
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('assunto_id', resposta.json()['campos'])
        pergunta.refresh_from_db()
        self.assertEqual(pergunta.assunto.tipo, 'oficial')
        oficial = Assunto.objects.oficiais().order_by('ordem').last()
        resposta = self.chamar('put', f'{ADMIN}/perguntas/{pergunta.id}', dados={**dados, 'assunto_id': str(oficial.id)})
        self.assertEqual(resposta.status_code, 200, resposta.content)
        pergunta.assunto = extra
        with self.assertRaises(ValidationError):
            pergunta.full_clean()

    def test_extras_fora_do_dashboard_e_da_lista_de_users(self):
        call_command('carregar_extras', stdout=StringIO())
        ativar_extras()
        ProgressoCard.objects.create(usuario=self.comum, card=Card.objects.get(codigo='EXA1'))
        corpo = self.chamar('get', '/api/admin/dashboard').json()
        self.assertEqual(len(corpo['conclusao_por_card']['cards']), 12)
        self.assertEqual(corpo['conclusao_por_card']['base'], 0)
        nao_iniciaram = next(g for g in corpo['situacao_contas']['grupos'] if g['chave'] == 'nao_iniciaram')
        self.assertEqual(nao_iniciaram['contas'], 1)
        users = self.chamar('get', '/api/admin/users').json()
        comum = next(i for i in users['itens'] if i['id'] == str(self.comum.id))
        self.assertEqual(comum['trilha'], {'concluidos': 0, 'total': 12})

    def test_admin_le_extras_sem_registrar(self):
        call_command('carregar_extras', stdout=StringIO())
        ativar_extras()
        corpo = self.chamar('get', '/api/trilha/extras').json()
        self.assertEqual(len(corpo['assuntos']), 2)
        self.assertFalse(ProgressoCard.objects.filter(usuario=self.admin).exists())
        self.assertFalse(TentativaQuiz.objects.exists())
        self.assertTrue(Usuario.objects.filter(pk=self.admin.pk).exists())
        self.assertTrue(Token.objects.filter(usuario=self.admin).exists())
