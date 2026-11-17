from unittest.mock import patch

from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client, TestCase
from django.utils import timezone

from users.models import Token, Usuario

from .models import (
    QUIZ_PERCENTUAL_APROVACAO, QUIZ_PERGUNTAS_POR_TENTATIVA, Card, Certificado, GuiaRapido, Opcao, Pergunta, ProgressoCard,
    ProgressoTrilha, TentativaPergunta, TentativaQuiz, Trilha,
)
from .services import aprovado


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

    def concluir_todos(self, exceto=()):
        for card in Card.objects.exclude(codigo__in=exceto):
            ProgressoCard.objects.create(usuario=self.usuario, card=card)

    def iniciar(self):
        resposta = self.post('/api/trilha/quiz/tentativas')
        self.assertEqual(resposta.status_code, 200, resposta.content)
        return resposta.json()

    def respostas(self, quiz, erros=0):
        respostas = {}
        for i, item in enumerate(quiz['perguntas']):
            opcoes = list(Opcao.objects.filter(pergunta_id=item['id']))
            certa = next(o for o in opcoes if o.correta)
            errada = next(o for o in opcoes if not o.correta)
            respostas[item['id']] = str((errada if i < erros else certa).id)
        return respostas

    def enviar(self, quiz, erros=0):
        return self.post('/api/trilha/quiz', {'tentativa_id': quiz['tentativa_id'], 'respostas': self.respostas(quiz, erros)})

    def deixar_ativas(self, quantidade):
        trilha = Trilha.objects.get()
        existentes = Pergunta.objects.count()
        for n in range(existentes, quantidade):
            pergunta = Pergunta.objects.create(
                trilha=trilha, codigo=f'X{n:02d}', enunciado=f'Pergunta extra {n}?', ordem=n + 1,
            )
            Opcao.objects.bulk_create(
                Opcao(pergunta=pergunta, texto=f'Opção {k}', correta=k == 0, ordem=k + 1) for k in range(4)
            )
        for pergunta in Pergunta.objects.order_by('ordem')[quantidade:]:
            pergunta.ativo = False
            pergunta.save()


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
        self.assertEqual(self.client.post('/api/trilha/quiz/tentativas').status_code, 401)


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
        self.assertEqual(len(corpo['guias_rapidos']), 1)
        self.assertEqual(len(corpo['guias_rapidos'][0]['passos']), 6)
        self.assertFalse(corpo['quiz']['liberado'])
        self.assertIsNone(corpo['certificado'])
        self.assertIsNone(corpo['trilha_concluida_em'])

    def test_ginecologista_e_o_quarto_card_de_cuidando_de_si(self):
        card = self.get('/api/trilha').json()['assuntos'][2]['cards'][3]
        self.assertEqual(card['tema'], 'Quando procurar o ginecologista')
        self.assertEqual(len(card['secoes']), 2)
        self.assertEqual(len(card['fontes']), 4)

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

    def test_concluir_o_ultimo_card_grava_a_conclusao_da_trilha(self):
        self.concluir_todos(exceto=['3.4'])
        self.assertFalse(ProgressoTrilha.objects.exists())
        self.post(f'/api/trilha/cards/{Card.objects.get(codigo="3.4").id}/concluir')
        conclusao = ProgressoTrilha.objects.get(usuario=self.usuario)
        self.assertIsNotNone(conclusao.trilha_concluida_em)
        self.assertTrue(self.get('/api/trilha').json()['quiz']['liberado'])

    def test_assunto_desativado_esconde_os_cards_sem_mudar_os_cards(self):
        card = Card.objects.get(codigo='1.1')
        assunto = card.assunto
        assunto.ativo = False
        assunto.save()
        corpo = self.get('/api/trilha').json()
        self.assertEqual(len(corpo['assuntos']), 2)
        self.assertEqual(corpo['total_cards'], 8)
        card.refresh_from_db()
        self.assertTrue(card.ativo)
        self.assertEqual(self.post(f'/api/trilha/cards/{card.id}/concluir').status_code, 404)

    def test_card_excluido_some_e_andamento_e_sobre_os_visiveis(self):
        ProgressoCard.objects.create(usuario=self.usuario, card=Card.objects.get(codigo='1.1'))
        ProgressoCard.objects.create(usuario=self.usuario, card=Card.objects.get(codigo='1.2'))
        Card.objects.filter(codigo='1.2').update(excluido_em=timezone.now())
        corpo = self.get('/api/trilha').json()
        self.assertEqual((corpo['concluidos'], corpo['total_cards']), (1, 11))
        dashboard = self.get('/api/dashboard').json()
        self.assertEqual((dashboard['concluidos'], dashboard['total'], dashboard['percentual']), (1, 11, 9))

    def test_guias_ativos_aparecem_na_ordem(self):
        GuiaRapido.objects.create(titulo='Segundo guia', passos=['Passo'], ordem=2)
        GuiaRapido.objects.create(titulo='Desativado', passos=['Passo'], ordem=3, ativo=False)
        GuiaRapido.objects.create(titulo='Excluído', passos=['Passo'], ordem=4, excluido_em=timezone.now())
        titulos = [g['titulo'] for g in self.get('/api/trilha').json()['guias_rapidos']]
        self.assertEqual(titulos, ['Menstruei, e agora?', 'Segundo guia'])


class ConclusaoDaTrilhaTests(BaseTrilhaTests):
    def test_card_excluido_nao_derruba_quem_concluiu(self):
        self.concluir_todos()
        self.get('/api/trilha')
        Card.objects.filter(codigo='1.1').update(excluido_em=timezone.now())
        corpo = self.get('/api/trilha').json()
        self.assertTrue(corpo['quiz']['liberado'])
        self.assertIsNotNone(corpo['trilha_concluida_em'])

    def test_card_novo_nao_desconclui(self):
        self.concluir_todos()
        concluida_em = self.get('/api/trilha').json()['trilha_concluida_em']
        assunto = Card.objects.get(codigo='1.1').assunto
        Card.objects.create(assunto=assunto, codigo='1.9', tema='Novo', explicacao='Texto', ordem=9)
        corpo = self.get('/api/trilha').json()
        self.assertEqual((corpo['concluidos'], corpo['total_cards']), (12, 13))
        self.assertTrue(corpo['quiz']['liberado'])
        self.assertEqual(corpo['trilha_concluida_em'], concluida_em)
        self.assertEqual(self.post('/api/trilha/quiz/tentativas').status_code, 200)

    def test_quem_estava_no_meio_e_ficou_com_tudo_concluido_faz_o_quiz(self):
        self.concluir_todos(exceto=['2.4'])
        self.assertEqual(self.post('/api/trilha/quiz/tentativas').status_code, 403)
        Card.objects.filter(codigo='2.4').update(excluido_em=timezone.now())
        self.assertEqual(self.post('/api/trilha/quiz/tentativas').status_code, 200)
        self.assertIsNotNone(ProgressoTrilha.objects.get(usuario=self.usuario).trilha_concluida_em)


class DashboardTests(BaseTrilhaTests):
    def test_percentual_por_assunto_e_geral(self):
        for codigo in ('1.1', '1.2', '2.1'):
            ProgressoCard.objects.create(usuario=self.usuario, card=Card.objects.get(codigo=codigo))
        corpo = self.get('/api/dashboard').json()
        self.assertEqual([a['percentual'] for a in corpo['assuntos']], [50, 25, 0])
        self.assertEqual(corpo['percentual'], 25)
        self.assertEqual(corpo['concluidos'], 3)


class CalculoDaNotaTests(TestCase):
    def test_aprovacao_so_com_inteiros_sobre_o_total_da_tentativa(self):
        self.assertEqual((QUIZ_PERGUNTAS_POR_TENTATIVA, QUIZ_PERCENTUAL_APROVACAO), (10, 70))
        self.assertFalse(aprovado(6, 9))
        self.assertTrue(aprovado(7, 9))
        self.assertFalse(aprovado(6, 10))
        self.assertTrue(aprovado(7, 10))
        self.assertFalse(aprovado(0, 0))


class QuizTests(BaseTrilhaTests):
    def test_quiz_bloqueado_ate_concluir_todos_os_cards(self):
        self.assertEqual(self.get('/api/trilha/quiz').status_code, 403)
        self.assertEqual(self.post('/api/trilha/quiz/tentativas').status_code, 403)
        ProgressoCard.objects.create(usuario=self.usuario, card=Card.objects.get(codigo='1.1'))
        self.assertEqual(self.post('/api/trilha/quiz/tentativas').status_code, 403)
        self.assertFalse(TentativaQuiz.objects.exists())

    def test_payload_do_user_nunca_contem_correta(self):
        self.concluir_todos()
        inicio = self.post('/api/trilha/quiz/tentativas')
        retomada = self.get('/api/trilha/quiz')
        trilha = self.get('/api/trilha')
        for resposta in (inicio, retomada, trilha):
            self.assertEqual(resposta.status_code, 200)
            self.assertNotIn('correta', resposta.content.decode())
        self.assertEqual(len(inicio.json()['perguntas']), 10)

    def test_sorteio_com_14_ativas_da_10_distintas(self):
        self.deixar_ativas(14)
        self.concluir_todos()
        quiz = self.iniciar()
        ids = [p['id'] for p in quiz['perguntas']]
        self.assertEqual((len(ids), len(set(ids)), quiz['total_perguntas']), (10, 10, 10))
        self.assertTrue(set(ids) <= {str(i) for i in Pergunta.objects.visiveis().values_list('id', flat=True)})

    def test_sorteio_com_10_e_com_9_ativas(self):
        self.concluir_todos()
        self.assertEqual(len(self.iniciar()['perguntas']), 10)
        TentativaQuiz.objects.all().delete()
        self.deixar_ativas(9)
        quiz = self.iniciar()
        self.assertEqual((len(quiz['perguntas']), quiz['total_perguntas']), (9, 9))

    def test_sem_perguntas_ativas_o_quiz_fica_indisponivel(self):
        self.concluir_todos()
        Pergunta.objects.update(ativo=False)
        resposta = self.post('/api/trilha/quiz/tentativas')
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json()['mensagem'], 'Quiz em atualização')
        estado = self.get('/api/trilha').json()['quiz']
        self.assertEqual((estado['disponivel'], estado['mensagem']), (False, 'Quiz em atualização'))

    def test_uma_pergunta_ativa_basta(self):
        self.concluir_todos()
        self.deixar_ativas(1)
        quiz = self.iniciar()
        resultado = self.enviar(quiz).json()
        self.assertEqual((resultado['acertos'], resultado['total_perguntas'], resultado['aprovada']), (1, 1, True))

    def test_retomar_mantem_as_mesmas_perguntas_na_mesma_ordem(self):
        self.deixar_ativas(14)
        self.concluir_todos()
        primeiro = self.iniciar()
        segundo = self.iniciar()
        retomado = self.get('/api/trilha/quiz').json()
        self.assertEqual(primeiro['tentativa_id'], segundo['tentativa_id'])
        ordem = [p['id'] for p in primeiro['perguntas']]
        self.assertEqual([p['id'] for p in segundo['perguntas']], ordem)
        self.assertEqual([p['id'] for p in retomado['perguntas']], ordem)
        self.assertEqual(TentativaQuiz.objects.count(), 1)

    def test_evita_repetir_a_ultima_tentativa_quando_possivel(self):
        self.deixar_ativas(20)
        self.concluir_todos()
        primeiro = self.iniciar()
        self.enviar(primeiro, erros=10)
        segundo = self.iniciar()
        self.assertFalse({p['id'] for p in primeiro['perguntas']} & {p['id'] for p in segundo['perguntas']})

    def test_com_poucas_novas_usa_todas_as_novas_e_completa_com_as_antigas(self):
        self.deixar_ativas(14)
        self.concluir_todos()
        primeiro = self.iniciar()
        self.enviar(primeiro, erros=10)
        usadas = {p['id'] for p in primeiro['perguntas']}
        novas = {str(i) for i in Pergunta.objects.visiveis().values_list('id', flat=True)} - usadas
        segundo = {p['id'] for p in self.iniciar()['perguntas']}
        self.assertEqual(len(segundo), 10)
        self.assertTrue(novas <= segundo)

    def test_opcoes_na_ordem_do_admin(self):
        self.concluir_todos()
        quiz = self.iniciar()
        for item in quiz['perguntas']:
            ordem = list(Opcao.objects.filter(pergunta_id=item['id'], ativo=True).order_by('ordem').values_list('id', flat=True))
            self.assertEqual([o['id'] for o in item['opcoes']], [str(i) for i in ordem])

    def test_aprovado_com_7_de_10_emite_certificado(self):
        self.concluir_todos()
        resultado = self.enviar(self.iniciar(), erros=3).json()
        self.assertEqual((resultado['acertos'], resultado['total_perguntas'], resultado['percentual']), (7, 10, 70))
        self.assertTrue(resultado['aprovada'])
        self.assertEqual(resultado['certificado']['nome_completo'], 'Maria Souza')
        self.assertEqual(resultado['certificado']['carga_horaria_minutos'], 60)
        self.assertEqual(TentativaPergunta.objects.filter(acertou=True).count(), 7)

    def test_6_de_10_reprova_e_indica_assuntos(self):
        self.concluir_todos()
        resultado = self.enviar(self.iniciar(), erros=4).json()
        self.assertFalse(resultado['aprovada'])
        self.assertEqual(resultado['percentual'], 60)
        self.assertIsNone(resultado['certificado'])
        self.assertTrue(resultado['assuntos_a_revisar'])
        self.assertEqual(self.get('/api/trilha/certificado').status_code, 404)

    def test_6_de_9_reprova_e_7_de_9_aprova(self):
        self.concluir_todos()
        self.deixar_ativas(9)
        reprovado = self.enviar(self.iniciar(), erros=3).json()
        self.assertEqual((reprovado['acertos'], reprovado['total_perguntas'], reprovado['aprovada']), (6, 9, False))
        aprovado_9 = self.enviar(self.iniciar(), erros=2).json()
        self.assertEqual((aprovado_9['acertos'], aprovado_9['total_perguntas'], aprovado_9['aprovada']), (7, 9, True))
        self.assertEqual(aprovado_9['percentual'], 78)

    def test_nova_aprovacao_nao_emite_segundo_certificado(self):
        self.concluir_todos()
        primeiro = self.enviar(self.iniciar()).json()['certificado']['codigo']
        segundo = self.enviar(self.iniciar()).json()['certificado']['codigo']
        self.assertEqual(primeiro, segundo)
        self.assertEqual(Certificado.objects.count(), 1)
        self.assertEqual(TentativaQuiz.objects.count(), 2)
        self.assertEqual(self.get('/api/trilha/certificado').json()['codigo'], primeiro)

    def test_envio_simultaneo_nao_quebra_quando_outro_emite_primeiro(self):
        self.concluir_todos()
        quiz = self.iniciar()
        with patch.object(Certificado.objects, 'create', side_effect=IntegrityError):
            resposta = self.enviar(quiz)
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()['aprovada'])
        self.assertEqual(TentativaQuiz.objects.count(), 1)

    def test_tentativa_ja_enviada_nao_e_corrigida_de_novo(self):
        self.concluir_todos()
        quiz = self.iniciar()
        self.assertEqual(self.enviar(quiz).status_code, 200)
        self.assertEqual(self.enviar(quiz).status_code, 409)

    def test_respostas_incompletas_ou_invalidas(self):
        self.concluir_todos()
        quiz = self.iniciar()
        respostas = self.respostas(quiz)
        parcial = dict(list(respostas.items())[:5])
        enviar = lambda r: self.post('/api/trilha/quiz', {'tentativa_id': quiz['tentativa_id'], 'respostas': r})
        self.assertEqual(enviar(parcial).status_code, 400)
        self.assertEqual(self.post('/api/trilha/quiz', {'tentativa_id': quiz['tentativa_id']}).status_code, 400)
        primeira, segunda = quiz['perguntas'][0]['id'], quiz['perguntas'][1]['id']
        trocada = {**respostas, primeira: respostas[segunda]}
        resposta = enviar(trocada)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('não pertence', resposta.json()['mensagem'])
        self.assertEqual(self.post('/api/trilha/quiz', {'respostas': respostas}).status_code, 404)
        self.assertFalse(TentativaQuiz.objects.filter(finalizada_em__isnull=False).exists())

    def test_pergunta_excluida_depois_nao_altera_nota_nem_certificado(self):
        self.concluir_todos()
        quiz = self.iniciar()
        self.enviar(quiz, erros=2)
        tentativa = TentativaQuiz.objects.get()
        Pergunta.objects.filter(pk=quiz['perguntas'][0]['id']).update(excluido_em=timezone.now(), ativo=False)
        tentativa.refresh_from_db()
        self.assertEqual((tentativa.acertos, tentativa.total_perguntas, tentativa.percentual, tentativa.aprovada), (8, 10, 80, True))
        self.assertEqual(self.get('/api/trilha/certificado').json()['aproveitamento_percentual'], 80)

    def test_pergunta_excluida_durante_a_tentativa_continua_sendo_corrigida(self):
        self.concluir_todos()
        quiz = self.iniciar()
        Pergunta.objects.filter(pk=quiz['perguntas'][0]['id']).update(excluido_em=timezone.now())
        resultado = self.enviar(quiz).json()
        self.assertEqual((resultado['acertos'], resultado['total_perguntas']), (10, 10))


class AdminSoVisualizaTests(BaseTrilhaTests):
    MENSAGEM = 'O perfil admin só visualiza a trilha, nada é registrado'

    def setUp(self):
        super().setUp()
        self.admin = Usuario(
            nome='Lia', sobrenome='Admin', apelido='lia', data_nascimento='10/04/1990',
            email='lia@exemplo.com', perfil=Usuario.Perfil.ADMIN,
        )
        self.admin.definir_senha('senha-12345')
        self.admin.save()
        self.cabecalho = {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=self.admin).chave}'}

    def nada_registrado(self):
        for modelo in (ProgressoCard, TentativaQuiz, Certificado, ProgressoTrilha):
            self.assertFalse(modelo.objects.filter(usuario=self.admin).exists(), modelo.__name__)

    def test_concluir_card_responde_403(self):
        card = Card.objects.get(codigo='1.1')
        resposta = self.post(f'/api/trilha/cards/{card.id}/concluir')
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.json()['mensagem'], self.MENSAGEM)
        self.nada_registrado()

    def test_iniciar_e_enviar_quiz_respondem_403(self):
        self.assertEqual(self.post('/api/trilha/quiz/tentativas').status_code, 403)
        resposta = self.post('/api/trilha/quiz', {'respostas': {}})
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.json()['mensagem'], self.MENSAGEM)
        self.nada_registrado()

    def test_certificado_responde_403(self):
        resposta = self.get('/api/trilha/certificado')
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(resposta.json()['mensagem'], self.MENSAGEM)

    def test_dashboard_pessoal_responde_403(self):
        resposta = self.get('/api/dashboard')
        self.assertEqual(resposta.status_code, 403)
        self.assertIn('Dashboard administrativo', resposta.json()['mensagem'])

    def test_trilha_abre_em_modo_visualizacao(self):
        resposta = self.get('/api/trilha')
        self.assertEqual(resposta.status_code, 200)
        corpo = resposta.json()
        self.assertTrue(corpo['modo_visualizacao'])
        self.assertEqual([len(a['cards']) for a in corpo['assuntos']], [4, 4, 4])
        self.assertTrue(corpo['quiz']['liberado'])
        self.assertIsNone(corpo['certificado'])
        self.nada_registrado()

    def test_quiz_abre_para_leitura_sem_concluir_cards(self):
        resposta = self.get('/api/trilha/quiz')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.json()['perguntas']), 10)
        self.assertIsNone(resposta.json()['tentativa_id'])
        self.assertNotIn('correta', resposta.content.decode())
        self.nada_registrado()

    def test_user_continua_registrando(self):
        user = {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=self.usuario).chave}'}
        card = Card.objects.get(codigo='1.1')
        resposta = self.client.post(f'/api/trilha/cards/{card.id}/concluir', **user)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(self.client.get('/api/trilha', **user).json()['modo_visualizacao'])
        self.assertEqual(self.client.get('/api/dashboard', **user).status_code, 200)
