from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone

from trilha.models import (
    Assunto, Card, FonteCard, GuiaRapido, Opcao, Pergunta, ProgressoCard, TentativaPergunta, TentativaQuiz,
)
from users.models import LogAtividade

from .tests import BaseAdminTests

URL = '/api/admin/conteudo'


class BaseConteudoTests(BaseAdminTests):
    def card(self, codigo='1.1'):
        return Card.objects.get(codigo=codigo)

    def detalhe(self, recurso, item_id):
        return self.chamar('get', f'{URL}/{recurso}/{item_id}').json()

    def acao(self, recurso, item_id, acao, dados=None):
        return self.chamar('post', f'{URL}/{recurso}/{item_id}/{acao}', dados=dados)

    def payload_card(self, card, **mudancas):
        atual = self.detalhe('cards', card.id)
        dados = {k: atual[k] for k in ('titulo', 'explicacao', 'exemplo', 'fontes', 'atualizado_em')}
        dados.update(mudancas)
        return dados

    def payload_pergunta(self, pergunta, **mudancas):
        atual = self.detalhe('perguntas', pergunta.id)
        dados = {'enunciado': atual['enunciado'], 'opcoes': atual['opcoes'], 'atualizado_em': atual['atualizado_em']}
        dados.update(mudancas)
        return dados

    def nova_pergunta(self, **mudancas):
        dados = {
            'enunciado': 'Quantos dias tem uma semana?',
            'opcoes': [
                {'texto': 'Cinco', 'correta': False}, {'texto': 'Seis', 'correta': False},
                {'texto': 'Sete', 'correta': True}, {'texto': 'Oito', 'correta': False},
            ],
        }
        dados.update(mudancas)
        return self.chamar('post', f'{URL}/perguntas', dados=dados)


class AcessoConteudoTests(BaseConteudoTests):
    def rotas_de_conteudo(self):
        card = self.card()
        assunto = card.assunto
        pergunta = Pergunta.objects.first()
        guia = GuiaRapido.objects.first()
        rotas = [('get', f'{URL}/quiz/resumo')]
        for recurso, item in (('assuntos', assunto), ('cards', card), ('perguntas', pergunta), ('guias', guia)):
            rotas += [
                ('get', f'{URL}/{recurso}'), ('post', f'{URL}/{recurso}'),
                ('get', f'{URL}/{recurso}/{item.id}'), ('put', f'{URL}/{recurso}/{item.id}'),
                ('get', f'{URL}/{recurso}/{item.id}/impacto'), ('get', f'{URL}/{recurso}/{item.id}/visualizar'),
            ]
            rotas += [('post', f'{URL}/{recurso}/{item.id}/{a}') for a in ('ativar', 'desativar', 'excluir', 'restaurar', 'reordenar')]
        return rotas

    def test_user_recebe_403_e_sem_token_401(self):
        for metodo, url in self.rotas_de_conteudo():
            self.assertEqual(self.chamar(metodo, url, auth=self.auth_comum).status_code, 403, f'{metodo} {url}')
            self.assertEqual(self.chamar(metodo, url, auth={}).status_code, 401, f'{metodo} {url}')
        self.assertTrue(Card.objects.filter(codigo='1.1', excluido_em__isnull=True).exists())

    def test_rotas_genericas_antigas_e_exclusao_fisica_nao_existem(self):
        self.assertEqual(self.chamar('get', f'{URL}/fontes').status_code, 404)
        self.assertEqual(self.chamar('get', f'{URL}/opcoes').status_code, 404)
        self.assertEqual(self.chamar('delete', f'{URL}/cards/{self.card().id}').status_code, 405)
        self.assertEqual(self.chamar('patch', f'{URL}/cards/{self.card().id}', dados={}).status_code, 405)
        self.assertTrue(Card.objects.filter(codigo='1.1').exists())


class ValidacaoPerguntaTests(BaseConteudoTests):
    def test_quantidade_de_opcoes(self):
        base = self.nova_pergunta().json()
        for quantidade in (3, 5):
            opcoes = [{'texto': f'Opção {i}', 'correta': i == 0} for i in range(quantidade)]
            resposta = self.nova_pergunta(opcoes=opcoes)
            self.assertEqual(resposta.status_code, 400, quantidade)
            self.assertIn('opcoes', resposta.json()['campos'])
        self.assertEqual(Pergunta.objects.filter(enunciado='Quantos dias tem uma semana?').count(), 1)
        self.assertTrue(base['id'])

    def test_exatamente_uma_correta(self):
        for corretas in (0, 2):
            opcoes = [{'texto': f'Opção {i}', 'correta': i < corretas} for i in range(4)]
            resposta = self.nova_pergunta(opcoes=opcoes)
            self.assertEqual(resposta.status_code, 400, corretas)
            self.assertEqual(resposta.json()['campos']['opcoes'], 'Marque exatamente uma opção correta.')

    def test_textos_vazios_e_repetidos(self):
        vazia = [{'texto': '  ', 'correta': True}, {'texto': 'B'}, {'texto': 'C'}, {'texto': 'D'}]
        resposta = self.nova_pergunta(opcoes=vazia)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('opcoes.0.texto', resposta.json()['campos'])
        repetida = [{'texto': 'Sete dias', 'correta': True}, {'texto': '  sete   DIAS '}, {'texto': 'C'}, {'texto': 'D'}]
        resposta = self.nova_pergunta(opcoes=repetida)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('opcoes.1.texto', resposta.json()['campos'])
        self.assertEqual(self.nova_pergunta(enunciado='   ').status_code, 400)
        self.assertEqual(self.nova_pergunta(enunciado='x' * 201).status_code, 400)
        longa = [{'texto': 'x' * 121, 'correta': True}, {'texto': 'B'}, {'texto': 'C'}, {'texto': 'D'}]
        self.assertEqual(self.nova_pergunta(opcoes=longa).status_code, 400)
        self.assertFalse(Pergunta.objects.filter(enunciado='Quantos dias tem uma semana?').exists())

    def test_ids_das_opcoes_preservados(self):
        pergunta = Pergunta.objects.get(codigo='Q01')
        ids = list(Opcao.objects.filter(pergunta=pergunta).order_by('ordem').values_list('id', flat=True))
        dados = self.payload_pergunta(pergunta)
        dados['opcoes'][0]['texto'] = 'Ovulação mensal'
        for opcao in dados['opcoes']:
            opcao['correta'] = opcao['texto'] == 'Puberdade'
        resposta = self.chamar('put', f'{URL}/perguntas/{pergunta.id}', dados=dados)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        depois = list(Opcao.objects.filter(pergunta=pergunta).order_by('ordem'))
        self.assertEqual([o.id for o in depois], ids)
        self.assertEqual(depois[0].texto, 'Ovulação mensal')
        self.assertEqual([o.texto for o in depois if o.correta], ['Puberdade'])

    def test_opcao_de_outra_pergunta_recusada(self):
        pergunta = Pergunta.objects.get(codigo='Q01')
        outra = Opcao.objects.filter(pergunta__codigo='Q02').first()
        dados = self.payload_pergunta(pergunta)
        dados['opcoes'][0]['id'] = str(outra.id)
        resposta = self.chamar('put', f'{URL}/perguntas/{pergunta.id}', dados=dados)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('opcoes.0.id', resposta.json()['campos'])

    def test_payload_admin_de_visualizacao_nao_traz_correta(self):
        pergunta = Pergunta.objects.get(codigo='Q01')
        resposta = self.chamar('get', f'{URL}/perguntas/{pergunta.id}/visualizar')
        self.assertTrue(resposta.json()['modo_visualizacao'])
        self.assertNotIn('correta', resposta.content.decode())


class ValidacaoCardTests(BaseConteudoTests):
    def novo_card(self, **mudancas):
        dados = {
            'assunto_id': str(self.card().assunto_id), 'titulo': 'Novo card', 'explicacao': 'Texto',
            'exemplo': '', 'fontes': [{'nome': 'OMS', 'url': 'https://www.who.int'}],
        }
        dados.update(mudancas)
        return self.chamar('post', f'{URL}/cards', dados=dados)

    def test_card_ativo_sem_fonte_recusado(self):
        resposta = self.novo_card(fontes=[])
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('fontes', resposta.json()['campos'])
        card = self.card()
        resposta = self.chamar('put', f'{URL}/cards/{card.id}', dados=self.payload_card(card, fontes=[]))
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(FonteCard.objects.filter(card=card).count(), 1)

    def test_card_desativado_pode_ficar_sem_fonte_mas_nao_ativa(self):
        card = self.card()
        self.acao('cards', card.id, 'desativar')
        resposta = self.chamar('put', f'{URL}/cards/{card.id}', dados=self.payload_card(card, fontes=[]))
        self.assertEqual(resposta.status_code, 200, resposta.content)
        ativar = self.acao('cards', card.id, 'ativar')
        self.assertEqual(ativar.status_code, 400)
        self.assertIn('fontes', ativar.json()['campos'])
        card.refresh_from_db()
        self.assertFalse(card.ativo)

    def test_url_invalida_recusada(self):
        for url in ('javascript:alert(1)', 'ftp://exemplo.com/a', 'exemplo.com', 'https://' + 'a' * 300 + '.com'):
            resposta = self.novo_card(fontes=[{'nome': 'Fonte', 'url': url}])
            self.assertEqual(resposta.status_code, 400, url)
            self.assertIn('fontes.0.url', resposta.json()['campos'])
        self.assertFalse(Card.objects.filter(tema='Novo card').exists())

    def test_limites_de_campos(self):
        for campo, tamanho in (('titulo', 81), ('explicacao', 601), ('exemplo', 256)):
            resposta = self.novo_card(**{campo: 'x' * tamanho})
            self.assertEqual(resposta.status_code, 400, campo)
            self.assertIn(campo, resposta.json()['campos'])
        resposta = self.novo_card(fontes=[{'nome': 'x' * 121, 'url': 'https://www.who.int'}])
        self.assertIn('fontes.0.nome', resposta.json()['campos'])

    def test_novo_card_entra_no_fim_com_fontes_na_ordem(self):
        fontes = [{'nome': 'B', 'url': 'https://b.org'}, {'nome': 'A', 'url': 'https://a.org'}]
        resposta = self.novo_card(fontes=fontes)
        self.assertEqual(resposta.status_code, 201, resposta.content)
        corpo = resposta.json()
        self.assertEqual(corpo['ordem'], 5)
        self.assertEqual(corpo['fontes'], fontes)
        user = self.chamar('get', '/api/trilha', auth=self.auth_comum).json()
        self.assertEqual(user['assuntos'][0]['cards'][-1]['fontes'], fontes)

    def test_atualizacao_atomica(self):
        card = self.card()
        fontes_antes = list(FonteCard.objects.filter(card=card).values_list('id', 'nome', 'url'))
        dados = self.payload_card(card, titulo='Título novo', fontes=[{'nome': 'Nova', 'url': 'https://nova.org'}])
        with patch('administracao.conteudo.registrar_log_admin', side_effect=RuntimeError('falhou')):
            with self.assertRaises(RuntimeError):
                self.chamar('put', f'{URL}/cards/{card.id}', dados=dados)
        card.refresh_from_db()
        self.assertEqual(card.tema, 'O que é a menstruação?')
        self.assertEqual(list(FonteCard.objects.filter(card=card).values_list('id', 'nome', 'url')), fontes_antes)

    def test_conflito_por_atualizado_em_antigo(self):
        card = self.card()
        antigo = self.payload_card(card)
        self.assertEqual(self.chamar('put', f'{URL}/cards/{card.id}', dados={**antigo, 'titulo': 'Primeira'}).status_code, 200)
        resposta = self.chamar('put', f'{URL}/cards/{card.id}', dados={**antigo, 'titulo': 'Segunda'})
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(
            resposta.json()['mensagem'], 'Este conteúdo foi alterado por outra pessoa. Recarregue para continuar.',
        )
        card.refresh_from_db()
        self.assertEqual(card.tema, 'Primeira')

    def test_edicao_preserva_secoes_e_chamada_final(self):
        card = self.card('3.4')
        secoes, cta = card.secoes, card.cta
        resposta = self.chamar('put', f'{URL}/cards/{card.id}', dados=self.payload_card(card, titulo='Ginecologista'))
        self.assertEqual(resposta.status_code, 200)
        card.refresh_from_db()
        self.assertEqual((card.secoes, card.cta), (secoes, cta))


class ExclusaoERestauracaoTests(BaseConteudoTests):
    def test_exclusao_em_cascata_e_restauracao_do_assunto(self):
        assunto = self.card('1.1').assunto
        self.acao('cards', self.card('1.4').id, 'excluir')
        self.assertEqual(self.acao('assuntos', assunto.id, 'excluir').status_code, 200)
        assunto.refresh_from_db()
        cards = Card.objects.filter(assunto=assunto)
        self.assertTrue(all(c.excluido_em for c in cards))
        self.assertEqual(
            {c.codigo for c in cards if c.excluido_em == assunto.excluido_em}, {'1.1', '1.2', '1.3'},
        )
        user = self.chamar('get', '/api/trilha', auth=self.auth_comum).json()
        self.assertEqual(user['total_cards'], 8)

        self.assertEqual(self.acao('assuntos', assunto.id, 'restaurar').status_code, 200)
        restaurados = set(Card.objects.filter(assunto=assunto, excluido_em__isnull=True).values_list('codigo', flat=True))
        self.assertEqual(restaurados, {'1.1', '1.2', '1.3'})
        self.assertIsNotNone(self.card('1.4').excluido_em)

    def test_restaurar_card_com_assunto_excluido_recusado(self):
        card = self.card('2.1')
        self.acao('cards', card.id, 'excluir')
        self.acao('assuntos', card.assunto_id, 'excluir')
        resposta = self.acao('cards', card.id, 'restaurar')
        self.assertEqual(resposta.status_code, 409)
        self.assertEqual(resposta.json()['mensagem'], 'Restaure o assunto antes')
        self.assertIsNotNone(self.card('2.1').excluido_em)

    def test_reordenar_sem_buracos(self):
        assunto = self.card('1.1').assunto
        ordens = lambda: list(Card.objects.filter(assunto=assunto).nao_excluidos().order_by('ordem').values_list('codigo', 'ordem'))
        self.acao('cards', self.card('1.2').id, 'excluir')
        self.assertEqual(ordens(), [('1.1', 1), ('1.3', 2), ('1.4', 3)])
        self.assertEqual(self.acao('cards', self.card('1.4').id, 'reordenar', {'direcao': 'subir'}).status_code, 200)
        self.assertEqual(ordens(), [('1.1', 1), ('1.4', 2), ('1.3', 3)])
        self.assertEqual(self.acao('cards', self.card('1.1').id, 'reordenar', {'direcao': 'subir'}).status_code, 400)
        self.assertEqual(self.acao('cards', self.card('1.1').id, 'reordenar', {'direcao': 'lado'}).status_code, 400)
        self.acao('cards', self.card('1.2').id, 'restaurar')
        self.assertEqual(ordens(), [('1.1', 1), ('1.4', 2), ('1.3', 3), ('1.2', 4)])

    def test_reordenar_perguntas_e_guias(self):
        primeira, segunda = Pergunta.objects.order_by('ordem')[:2]
        self.acao('perguntas', segunda.id, 'reordenar', {'direcao': 'subir'})
        self.assertEqual(list(Pergunta.objects.order_by('ordem')[:2]), [segunda, primeira])
        outro = self.chamar('post', f'{URL}/guias', dados={'titulo': 'Outro guia', 'passos': ['Passo um']}).json()
        self.acao('guias', outro['id'], 'reordenar', {'direcao': 'subir'})
        titulos = [g['titulo'] for g in self.chamar('get', '/api/trilha', auth=self.auth_comum).json()['guias_rapidos']]
        self.assertEqual(titulos, ['Outro guia', 'Menstruei, e agora?'])

    def test_card_excluido_nao_derruba_quem_concluiu_e_impacto_conta_pessoas(self):
        for card in Card.objects.all():
            ProgressoCard.objects.create(usuario=self.comum, card=card)
        self.chamar('get', '/api/trilha', auth=self.auth_comum)
        card = self.card('1.1')
        self.assertEqual(self.chamar('get', f'{URL}/cards/{card.id}/impacto').json(), {'pessoas_concluiram': 1})
        self.acao('cards', card.id, 'excluir')
        user = self.chamar('get', '/api/trilha', auth=self.auth_comum).json()
        self.assertTrue(user['quiz']['liberado'])
        self.assertTrue(ProgressoCard.objects.filter(card=card).exists())

    def test_impactos_e_resumo_do_quiz(self):
        assunto = self.card('1.1').assunto
        self.assertEqual(self.chamar('get', f'{URL}/assuntos/{assunto.id}/impacto').json(), {'cards': 4})
        guia = GuiaRapido.objects.first()
        self.assertEqual(self.chamar('get', f'{URL}/guias/{guia.id}/impacto').json(), {'passos': 6})
        pergunta = Pergunta.objects.get(codigo='Q01')
        tentativa = TentativaQuiz.objects.create(
            usuario=self.comum, trilha=pergunta.trilha, total_perguntas=1, acertos=1, percentual=100, aprovada=True,
            finalizada_em=timezone.now(),
        )
        TentativaPergunta.objects.create(
            tentativa=tentativa, pergunta=pergunta, ordem=1, opcao_escolhida=pergunta.opcoes.first(), acertou=False,
        )
        self.assertEqual(self.chamar('get', f'{URL}/perguntas/{pergunta.id}/impacto').json(), {'pessoas_responderam': 1})
        self.assertEqual(
            self.chamar('get', f'{URL}/quiz/resumo').json(), {'cadastradas': 10, 'ativas': 10, 'por_tentativa': 10},
        )
        self.acao('perguntas', pergunta.id, 'desativar')
        self.acao('perguntas', Pergunta.objects.get(codigo='Q02').id, 'excluir')
        self.assertEqual(
            self.chamar('get', f'{URL}/quiz/resumo').json(), {'cadastradas': 9, 'ativas': 8, 'por_tentativa': 8},
        )

    def test_listagem_por_situacao(self):
        pergunta = Pergunta.objects.get(codigo='Q01')
        self.acao('perguntas', pergunta.id, 'excluir')
        ids = lambda s: {p['id'] for p in self.chamar('get', f'{URL}/perguntas?situacao={s}').json()['itens']}
        self.assertNotIn(str(pergunta.id), ids('ativos'))
        self.assertEqual(ids('excluidos'), {str(pergunta.id)})
        self.assertEqual(len(ids('todos')), 10)
        self.assertEqual(self.chamar('get', f'{URL}/perguntas?situacao=outra').status_code, 400)

    def test_editar_excluido_e_recusado(self):
        card = self.card()
        dados = self.payload_card(card)
        self.acao('cards', card.id, 'excluir')
        resposta = self.chamar('put', f'{URL}/cards/{card.id}', dados={**dados, 'atualizado_em': self.detalhe('cards', card.id)['atualizado_em']})
        self.assertEqual(resposta.status_code, 409)


class VisualizacaoELogsTests(BaseConteudoTests):
    def test_visualizar_devolve_o_payload_do_user_sem_registrar_nada(self):
        card = self.card()
        corpo = self.chamar('get', f'{URL}/cards/{card.id}/visualizar').json()
        self.assertTrue(corpo['modo_visualizacao'])
        self.assertEqual(corpo['card']['tema'], 'O que é a menstruação?')
        guia = GuiaRapido.objects.first()
        self.assertEqual(len(self.chamar('get', f'{URL}/guias/{guia.id}/visualizar').json()['guia']['passos']), 6)
        self.assertFalse(ProgressoCard.objects.exists())
        self.assertFalse(TentativaQuiz.objects.exists())

    def test_logs_com_ator_e_alvo(self):
        card = self.card()
        self.chamar('put', f'{URL}/cards/{card.id}', dados=self.payload_card(card, titulo='Título trocado'))
        self.acao('cards', card.id, 'desativar')
        self.acao('cards', card.id, 'ativar')
        self.acao('cards', card.id, 'reordenar', {'direcao': 'descer'})
        self.acao('cards', card.id, 'excluir')
        self.acao('cards', card.id, 'restaurar')
        criada = self.nova_pergunta().json()
        esperados = {
            LogAtividade.Acao.ADMIN_CONTEUDO_EDITADO: ('card', card.id),
            LogAtividade.Acao.ADMIN_CONTEUDO_DESATIVADO: ('card', card.id),
            LogAtividade.Acao.ADMIN_CONTEUDO_ATIVADO: ('card', card.id),
            LogAtividade.Acao.ADMIN_CONTEUDO_REORDENADO: ('card', card.id),
            LogAtividade.Acao.ADMIN_CONTEUDO_EXCLUIDO: ('card', card.id),
            LogAtividade.Acao.ADMIN_CONTEUDO_RESTAURADO: ('card', card.id),
            LogAtividade.Acao.ADMIN_CONTEUDO_CRIADO: ('pergunta_quiz', criada['id']),
        }
        for acao, (tipo, alvo) in esperados.items():
            log = self.logs(acao).get()
            self.assertEqual((log.ator, log.alvo_tipo, log.alvo_id), (self.admin, tipo, str(alvo)), acao)
        edicao = self.logs(LogAtividade.Acao.ADMIN_CONTEUDO_EDITADO).get()
        self.assertEqual(edicao.resumo['campos'], ['titulo'])
        self.assertEqual(edicao.resumo['depois'], {'titulo': 'Título trocado'})

    def test_resumo_do_log_truncado_em_120(self):
        card = self.card()
        self.chamar('put', f'{URL}/cards/{card.id}', dados=self.payload_card(card, explicacao='y' * 600))
        log = self.logs(LogAtividade.Acao.ADMIN_CONTEUDO_EDITADO).get()
        self.assertEqual(len(log.resumo['depois']['explicacao']), 120)
        self.assertEqual(len(log.resumo['antes']['explicacao']), 120)


class CarregarTrilhaTests(BaseConteudoTests):
    def test_idempotente_nao_sobrescreve_nao_restaura_nao_reordena(self):
        card = self.card('1.1')
        self.chamar('put', f'{URL}/cards/{card.id}', dados=self.payload_card(card, titulo='Tema editado'))
        self.acao('cards', self.card('1.2').id, 'excluir')
        self.acao('cards', self.card('1.4').id, 'reordenar', {'direcao': 'subir'})
        ordem = list(Card.objects.order_by('assunto__ordem', 'ordem').values_list('codigo', 'ordem'))
        opcoes, perguntas, assuntos = Opcao.objects.count(), Pergunta.objects.count(), Assunto.objects.count()

        call_command('carregar_trilha', verbosity=0)

        self.assertEqual(self.card('1.1').tema, 'Tema editado')
        self.assertIsNotNone(self.card('1.2').excluido_em)
        self.assertEqual(list(Card.objects.order_by('assunto__ordem', 'ordem').values_list('codigo', 'ordem')), ordem)
        self.assertEqual((Opcao.objects.count(), Pergunta.objects.count(), Assunto.objects.count()), (opcoes, perguntas, assuntos))
        self.assertEqual(GuiaRapido.objects.count(), 1)

    def test_cria_so_o_que_falta(self):
        Card.objects.filter(codigo='3.4').update(codigo='3.4X')
        call_command('carregar_trilha', verbosity=0)
        novo = self.card('3.4')
        self.assertEqual(novo.ordem, 5)
        self.assertEqual(Card.objects.filter(codigo__startswith='3.4').count(), 2)
