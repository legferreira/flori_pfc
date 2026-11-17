from datetime import timedelta

from django.template.loader import render_to_string
from django.utils import timezone

from trilha.models import Card, ProgressoCard, TentativaQuiz
from users.models import LogAtividade, Usuario
from users.services import ExcluirConta, mascarar_email

from .tests import BaseAdminTests, criar_usuario

URL = '/api/admin/users'


class BaseUsersTests(BaseAdminTests):
    def listar(self, **filtros):
        consulta = '&'.join(f'{k}={v}' for k, v in filtros.items())
        resposta = self.chamar('get', f'{URL}?{consulta}' if consulta else URL)
        self.assertEqual(resposta.status_code, 200, resposta.content)
        return resposta.json()

    def item(self, corpo, usuario):
        return next(i for i in corpo['itens'] if i['id'] == str(usuario.id))

    def excluir(self, usuario, **dados):
        return self.chamar('post', f'{URL}/{usuario.id}/excluir', dados=dados)

    def entrar(self, usuario, quando):
        LogAtividade.objects.create(usuario=usuario, acao=LogAtividade.Acao.LOGIN_SUCESSO, criado_em=quando)


class PermissaoUsersTests(BaseUsersTests):
    def test_user_comum_403_e_sem_token_401(self):
        alvo = criar_usuario('alvo@exemplo.com')
        for metodo, url in (('get', URL), ('post', f'{URL}/{alvo.id}/excluir')):
            self.assertEqual(self.chamar(metodo, url, auth=self.auth_comum, dados={'motivo': 'outro'}).status_code, 403)
            self.assertEqual(self.chamar(metodo, url, auth={}, dados={'motivo': 'outro'}).status_code, 401)
        self.assertTrue(Usuario.objects.get(pk=alvo.pk).ativo)

    def test_nao_existe_rota_de_edicao_nem_rotas_antigas(self):
        self.assertEqual(self.chamar('get', '/api/admin/usuarios').status_code, 404)
        for metodo in ('put', 'patch', 'delete'):
            self.assertEqual(self.chamar(metodo, f'{URL}/{self.comum.id}', dados={'apelido': 'x'}).status_code, 404)
            self.assertEqual(self.chamar(metodo, URL, dados={}).status_code, 405)
        self.assertEqual(self.chamar('get', f'{URL}/{self.comum.id}/excluir').status_code, 405)


class ListagemUsersTests(BaseUsersTests):
    def test_campos_e_mascara_do_email(self):
        corpo = self.listar()
        item = self.item(corpo, self.comum)
        self.assertEqual(set(item), {
            'id', 'apelido', 'email_mascarado', 'cadastro', 'perfil', 'trilha', 'quiz', 'ultima_entrada', 'situacao',
            'excluida_em', 'demo',
        })
        self.assertEqual(item['email_mascarado'], 'co****@exemplo.com')
        self.assertEqual(set(corpo), {'pagina', 'por_pagina', 'total', 'total_paginas', 'itens'})
        self.assertEqual(mascarar_email('ab@x.com'), 'a****@x.com')
        self.assertEqual(mascarar_email('a@x.com'), '****@x.com')

    def test_trilha_quiz_e_ultima_entrada(self):
        for card in Card.objects.order_by('codigo')[:3]:
            ProgressoCard.objects.create(usuario=self.comum, card=card)
        Card.objects.filter(codigo='3.4').update(excluido_em=timezone.now())
        ProgressoCard.objects.create(usuario=self.comum, card=Card.objects.get(codigo='3.4'))
        trilha = Card.objects.first().assunto.trilha
        TentativaQuiz.objects.create(
            usuario=self.comum, trilha=trilha, total_perguntas=10, acertos=5, percentual=50, aprovada=False,
            finalizada_em=timezone.now(),
        )
        TentativaQuiz.objects.create(usuario=self.comum, trilha=trilha, total_perguntas=10)
        quando = timezone.now() - timedelta(hours=3)
        self.entrar(self.comum, quando - timedelta(days=2))
        self.entrar(self.comum, quando)
        LogAtividade.objects.create(usuario=self.comum, acao=LogAtividade.Acao.LOGOUT)

        item = self.item(self.listar(), self.comum)
        self.assertEqual(item['trilha'], {'concluidos': 3, 'total': 11})
        self.assertEqual(item['quiz'], 'nao_aprovada')
        self.assertEqual(item['ultima_entrada'], timezone.localtime(quando).isoformat())

        TentativaQuiz.objects.create(
            usuario=self.comum, trilha=trilha, total_perguntas=10, acertos=8, percentual=80, aprovada=True,
            finalizada_em=timezone.now(),
        )
        self.assertEqual(self.item(self.listar(), self.comum)['quiz'], 'aprovada')
        outra = criar_usuario('nova@exemplo.com')
        nova = self.item(self.listar(), outra)
        self.assertEqual((nova['quiz'], nova['trilha'], nova['ultima_entrada']), ('nao_tentou', {'concluidos': 0, 'total': 11}, None))

    def test_admin_sem_trilha_e_quiz_e_demo_marcado(self):
        demo = criar_usuario('demo01@demo.flori.test')
        Usuario.objects.filter(pk=demo.pk).update(demo=True)
        corpo = self.listar()
        admin = self.item(corpo, self.admin)
        self.assertEqual((admin['perfil'], admin['trilha'], admin['quiz']), ('admin', None, None))
        self.assertTrue(self.item(corpo, demo)['demo'])
        self.assertFalse(self.item(corpo, self.comum)['demo'])

    def test_conta_excluida_sem_trilha_nem_quiz(self):
        saiu = criar_usuario('saiu@exemplo.com')
        ExcluirConta(saiu.id).executar()
        item = self.item(self.listar(situacao='excluidas'), saiu)
        self.assertEqual(item['apelido'], 'Conta excluída')
        self.assertEqual((item['situacao'], item['trilha'], item['quiz'], item['email_mascarado']), ('excluida', None, None, None))
        self.assertIsNotNone(item['excluida_em'])
        self.assertIsNotNone(item['cadastro'])

    def test_filtro_de_situacao(self):
        saiu = criar_usuario('saiu@exemplo.com')
        ExcluirConta(saiu.id).executar()
        ids = lambda **f: {i['id'] for i in self.listar(**f)['itens']}
        self.assertNotIn(str(saiu.id), ids())
        self.assertEqual(ids(situacao='excluidas'), {str(saiu.id)})
        self.assertEqual(len(ids(situacao='todas')), 3)
        resposta = self.chamar('get', f'{URL}?situacao=ativos')
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('situacao', resposta.json()['campos'])
        self.assertIn('ordem', self.chamar('get', f'{URL}?ordem=apelido').json()['campos'])

    def test_busca_so_por_apelido(self):
        bia = criar_usuario('outra.coisa@exemplo.com')
        Usuario.objects.filter(pk=bia.pk).update(apelido='Biazinha', celular='11999998888')
        self.assertEqual({i['apelido'] for i in self.listar(busca='BIAZ')['itens']}, {'Biazinha'})
        self.assertEqual(self.listar(busca='outra.coisa')['total'], 0)
        self.assertEqual(self.listar(busca='exemplo.com')['total'], 0)
        self.assertEqual(self.listar(busca='11999998888')['total'], 0)
        self.assertEqual(self.listar(busca='com')['total'], 1)

    def test_ordem(self):
        antiga = criar_usuario('antiga@exemplo.com')
        Usuario.objects.filter(pk=antiga.pk).update(criado_em=timezone.now() - timedelta(days=30))
        recente = criar_usuario('recente@exemplo.com')
        self.entrar(antiga, timezone.now())
        self.entrar(self.comum, timezone.now() - timedelta(days=1))
        ordem = lambda **f: [i['id'] for i in self.listar(**f)['itens']]
        self.assertEqual(ordem()[0], str(recente.id))
        self.assertEqual(ordem(ordem='cadastro_asc')[0], str(antiga.id))
        por_entrada = ordem(ordem='entrada_desc')
        self.assertEqual(por_entrada[:2], [str(antiga.id), str(self.comum.id)])

    def test_paginacao_fixa_em_20(self):
        for n in range(23):
            criar_usuario(f'pessoa{n:02d}@exemplo.com')
        primeira = self.listar()
        self.assertEqual((len(primeira['itens']), primeira['total'], primeira['total_paginas']), (20, 25, 2))
        segunda = self.listar(pagina=2)
        self.assertEqual(len(segunda['itens']), 5)
        self.assertEqual(len(self.listar(por_pagina=5)['itens']), 20)
        self.assertEqual(self.listar(pagina=99)['pagina'], 2)
        self.assertFalse({i['id'] for i in primeira['itens']} & {i['id'] for i in segunda['itens']})

    def test_listar_gera_log(self):
        self.listar(busca='ana')
        log = self.logs(LogAtividade.Acao.ADMIN_LISTOU_USUARIOS).get()
        self.assertEqual(log.resumo['com_busca'], True)
        self.assertNotIn('ana', str(log.resumo))


class ExclusaoUsersTests(BaseUsersTests):
    def test_exige_motivo_da_lista(self):
        for motivo in (None, '', '  ', 'pedido_do_titular', 'OUTRO'):
            resposta = self.excluir(self.comum, motivo=motivo)
            self.assertEqual(resposta.status_code, 400, motivo)
            self.assertIn('motivo', resposta.json()['campos'])
        self.assertTrue(Usuario.objects.get(pk=self.comum.pk).ativo)

    def test_observacao_ate_140(self):
        resposta = self.excluir(self.comum, motivo='outro', observacao='x' * 141)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn('observacao', resposta.json()['campos'])
        self.assertTrue(Usuario.objects.get(pk=self.comum.pk).ativo)
        self.assertEqual(self.excluir(self.comum, motivo='outro', observacao='x' * 140).status_code, 204)

    def test_exclui_reusando_o_servico_e_registra_log_sem_email_nem_observacao(self):
        ProgressoCard.objects.create(usuario=self.comum, card=Card.objects.first())
        resposta = self.excluir(self.comum, motivo='conta_duplicada', observacao='veio pelo email comum@exemplo.com')
        self.assertEqual(resposta.status_code, 204)
        conta = Usuario.objects.get(pk=self.comum.pk)
        self.assertFalse(conta.ativo)
        self.assertIsNone(conta.email)
        self.assertEqual(conta.apelido, 'Conta excluída')
        self.assertFalse(ProgressoCard.objects.filter(usuario=conta).exists())
        log = self.logs(LogAtividade.Acao.ADMIN_USER_EXCLUIDO).get()
        self.assertEqual((log.ator, log.alvo_tipo, log.alvo_id), (self.admin, 'usuario', str(conta.id)))
        self.assertEqual(log.resumo, {'motivo': 'conta_duplicada'})
        todos = ' '.join(str(l.resumo) + l.alvo_id for l in LogAtividade.objects.all())
        self.assertNotIn('comum@exemplo.com', todos)
        self.assertNotIn('veio pelo', todos)
        self.notificacao.return_value.enviar_conta_excluida.assert_called_once_with(
            'comum@exemplo.com', 'comum', pelo_admin=True,
        )

    def test_nao_exclui_admin_a_si_mesmo_nem_duas_vezes(self):
        outro = criar_usuario('outro@exemplo.com', perfil=Usuario.Perfil.ADMIN)
        self.assertEqual(self.excluir(outro, motivo='outro').status_code, 403)
        self.assertEqual(self.excluir(self.admin, motivo='outro').status_code, 403)
        self.assertTrue(Usuario.objects.get(pk=outro.pk).ativo)
        self.assertTrue(Usuario.objects.get(pk=self.admin.pk).ativo)
        self.assertEqual(self.excluir(self.comum, motivo='conta_teste').status_code, 204)
        self.assertEqual(self.excluir(self.comum, motivo='conta_teste').status_code, 409)
        self.assertEqual(self.logs(LogAtividade.Acao.ADMIN_USER_EXCLUIDO).count(), 1)
        self.assertEqual(self.chamar('post', f'{URL}/00000000-0000-0000-0000-000000000000/excluir', dados={'motivo': 'outro'}).status_code, 404)

    def test_texto_do_email_e_neutro(self):
        texto = render_to_string('users/emails/conta_excluida.txt', {'apelido': 'Bia', 'pelo_admin': True})
        self.assertIn('Sua conta no Flori foi excluída pela administração', texto)
        for motivo in ('motivo', 'violação', 'duplicada', 'teste'):
            self.assertNotIn(motivo, texto.lower())


class EmailCompletoNuncaApareceTests(BaseUsersTests):
    def test_nenhuma_resposta_admin_traz_email_completo(self):
        ProgressoCard.objects.create(usuario=self.comum, card=Card.objects.first())
        saiu = criar_usuario('saiu@exemplo.com')
        ExcluirConta(saiu.id).executar()
        emails = [u.email for u in Usuario.objects.exclude(email__isnull=True)] + ['saiu@exemplo.com']
        respostas = [
            self.chamar('get', URL), self.chamar('get', f'{URL}?situacao=todas'),
            self.chamar('get', f'{URL}?ordem=entrada_desc'), self.chamar('get', '/api/admin/dashboard'),
            self.chamar('get', '/api/admin/conteudo/assuntos?situacao=todos'),
            self.excluir(self.comum, motivo='outro'), self.excluir(self.comum, motivo='outro'),
        ]
        for resposta in respostas:
            corpo = resposta.content.decode()
            for email in emails:
                self.assertNotIn(email, corpo, resposta.request['PATH_INFO'])
