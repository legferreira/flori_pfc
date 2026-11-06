from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client, TestCase

from users.models import Token, Usuario

from .models import Card, Certificado, Pergunta, ProgressoCard, TentativaQuiz


class BaseTrilhaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('carregar_trilha', verbosity=0)

    def setUp(self):
        self.usuario = Usuario(
            nome='Maria', sobrenome='Souza', apelido='mari',
            data_nascimento='10/04/2008', email='maria@exemplo.com',
        )
        self.usuario.definir_senha('senha-12345')
        self.usuario.save()
        self.cabecalho = {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=self.usuario).chave}'}

    def get(self, url):
        return self.client.get(url, **self.cabecalho)

    def post(self, url, dados=None):
        return self.client.post(url, dados or {}, content_type='application/json', **self.cabecalho)

    def concluir_todos(self):
        for card in Card.objects.all():
            ProgressoCard.objects.create(usuario=self.usuario, card=card)

    def respostas(self, erros=0):
        respostas = {}
        for i, pergunta in enumerate(Pergunta.objects.prefetch_related('opcoes')):
            opcoes = list(pergunta.opcoes.all())
            certa = next(o for o in opcoes if o.correta)
            errada = next(o for o in opcoes if not o.correta)
            respostas[str(pergunta.id)] = str((errada if i < erros else certa).id)
        return respostas


class CargaDoConteudoTests(BaseTrilhaTests):
    def test_carrega_12_cards_e_10_perguntas(self):
        self.assertEqual(Card.objects.count(), 12)
        self.assertEqual(Pergunta.objects.count(), 10)

    def test_cada_pergunta_tem_uma_unica_resposta_certa(self):
        for pergunta in Pergunta.objects.all():
            self.assertEqual(pergunta.opcoes.filter(correta=True).count(), 1, pergunta.codigo)

    def test_rodar_de_novo_nao_duplica(self):
        call_command('carregar_trilha', verbosity=0)
        self.assertEqual(Card.objects.count(), 12)
        self.assertEqual(Pergunta.objects.count(), 10)


class AutenticacaoTests(BaseTrilhaTests):
    def test_rotas_exigem_token(self):
        for url in ('/api/trilha', '/api/trilha/quiz', '/api/trilha/certificado', '/api/dashboard'):
            self.assertEqual(self.client.get(url).status_code, 401, url)


class CsrfTests(BaseTrilhaTests):
    def test_post_com_token_funciona_mesmo_com_checagem_de_csrf_ligada(self):
        card = Card.objects.get(codigo='1.1')
        cliente = Client(enforce_csrf_checks=True)
        resposta = cliente.post(
            f'/api/trilha/cards/{card.id}/concluir', content_type='application/json',
            HTTP_ORIGIN='http://127.0.0.1:5500', **self.cabecalho,
        )
        self.assertEqual(resposta.status_code, 200)


class TrilhaTests(BaseTrilhaTests):
    def test_lista_assuntos_cards_e_guia(self):
        corpo = self.get('/api/trilha').json()
        self.assertEqual([len(a['cards']) for a in corpo['assuntos']], [4, 4, 4])
        self.assertEqual(corpo['total_cards'], 12)
        self.assertEqual(corpo['concluidos'], 0)
        self.assertEqual(len(corpo['guia_rapido']['passos']), 6)
        self.assertFalse(corpo['quiz']['liberado'])
        self.assertIsNone(corpo['certificado'])

    def test_ginecologista_e_o_quarto_card_de_cuidando_de_si(self):
        card = self.get('/api/trilha').json()['assuntos'][2]['cards'][3]
        self.assertEqual(card['tema'], 'Quando procurar o ginecologista')
        self.assertEqual(len(card['secoes']), 2)

    def test_concluir_card_e_idempotente(self):
        card = Card.objects.get(codigo='1.1')
        url = f'/api/trilha/cards/{card.id}/concluir'
        primeira = self.post(url)
        segunda = self.post(url)
        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(primeira.json()['concluido_em'], segunda.json()['concluido_em'])
        self.assertEqual(ProgressoCard.objects.filter(usuario=self.usuario).count(), 1)

    def test_card_inexistente(self):
        resposta = self.post('/api/trilha/cards/00000000-0000-0000-0000-000000000000/concluir')
        self.assertEqual(resposta.status_code, 404)

    def test_progresso_de_uma_usuaria_nao_aparece_para_outra(self):
        self.concluir_todos()
        outra = Usuario(nome='Bia', sobrenome='Lima', apelido='bia', data_nascimento='01/01/2008', email='bia@exemplo.com')
        outra.definir_senha('senha-12345')
        outra.save()
        cabecalho = {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=outra).chave}'}
        corpo = self.client.get('/api/trilha', **cabecalho).json()
        self.assertEqual(corpo['concluidos'], 0)


class DashboardTests(BaseTrilhaTests):
    def test_percentual_por_assunto_e_geral(self):
        for codigo in ('1.1', '1.2', '2.1'):
            ProgressoCard.objects.create(usuario=self.usuario, card=Card.objects.get(codigo=codigo))
        corpo = self.get('/api/dashboard').json()
        self.assertEqual([a['percentual'] for a in corpo['assuntos']], [50, 25, 0])
        self.assertEqual(corpo['percentual'], 25)
        self.assertEqual(corpo['concluidos'], 3)


class QuizTests(BaseTrilhaTests):
    def test_quiz_bloqueado_ate_concluir_todos_os_cards(self):
        self.assertEqual(self.get('/api/trilha/quiz').status_code, 403)
        self.assertEqual(self.post('/api/trilha/quiz', {'respostas': self.respostas()}).status_code, 403)
        ProgressoCard.objects.create(usuario=self.usuario, card=Card.objects.get(codigo='1.1'))
        self.assertEqual(self.get('/api/trilha/quiz').status_code, 403)

    def test_quiz_liberado_nao_revela_respostas_certas(self):
        self.concluir_todos()
        resposta = self.get('/api/trilha/quiz')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.json()['perguntas']), 10)
        self.assertNotIn('correta', resposta.content.decode())

    def test_aprovado_com_70_por_cento_emite_certificado(self):
        self.concluir_todos()
        resultado = self.post('/api/trilha/quiz', {'respostas': self.respostas(erros=3)}).json()
        self.assertEqual((resultado['acertos'], resultado['percentual']), (7, 70))
        self.assertTrue(resultado['aprovada'])
        self.assertEqual(resultado['certificado']['nome_completo'], 'Maria Souza')
        self.assertEqual(resultado['certificado']['carga_horaria_minutos'], 60)

    def test_reprovado_indica_assuntos_para_revisar_e_nao_emite(self):
        self.concluir_todos()
        resultado = self.post('/api/trilha/quiz', {'respostas': self.respostas(erros=4)}).json()
        self.assertFalse(resultado['aprovada'])
        self.assertEqual(resultado['percentual'], 60)
        self.assertIsNone(resultado['certificado'])
        self.assertEqual([a['titulo'] for a in resultado['assuntos_a_revisar']], ['Começando', 'Entendendo o ciclo'])
        self.assertEqual(self.get('/api/trilha/certificado').status_code, 404)

    def test_nova_aprovacao_nao_emite_segundo_certificado(self):
        self.concluir_todos()
        primeiro = self.post('/api/trilha/quiz', {'respostas': self.respostas()}).json()['certificado']['codigo']
        segundo = self.post('/api/trilha/quiz', {'respostas': self.respostas()}).json()['certificado']['codigo']
        self.assertEqual(primeiro, segundo)
        self.assertEqual(Certificado.objects.count(), 1)
        self.assertEqual(TentativaQuiz.objects.count(), 2)
        self.assertEqual(self.get('/api/trilha/certificado').json()['codigo'], primeiro)

    def test_envio_simultaneo_nao_quebra_quando_outro_emite_primeiro(self):
        self.concluir_todos()
        with patch.object(Certificado.objects, 'create', side_effect=IntegrityError):
            resposta = self.post('/api/trilha/quiz', {'respostas': self.respostas()})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()['aprovada'])
        self.assertEqual(TentativaQuiz.objects.count(), 1)

    def test_respostas_incompletas_ou_invalidas(self):
        self.concluir_todos()
        parcial = dict(list(self.respostas().items())[:5])
        self.assertEqual(self.post('/api/trilha/quiz', {'respostas': parcial}).status_code, 400)
        self.assertEqual(self.post('/api/trilha/quiz', {}).status_code, 400)
        self.assertEqual(TentativaQuiz.objects.count(), 0)
