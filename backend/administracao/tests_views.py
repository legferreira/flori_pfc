from trilha.models import Card
from users.models import Consentimento, Token, Usuario

from .tests import BaseAdminTests, criar_usuario


class EntradasInvalidasAdminTests(BaseAdminTests):
    def bruto(self, metodo, url, corpo='{nao e json'):
        return getattr(self.client, metodo)(url, corpo, content_type='application/json', **self.auth_admin)

    def test_json_invalido_responde_400_sem_alterar_nada(self):
        card = Card.objects.get(codigo='1.1')
        rotas = [
            ('post', f'/api/admin/users/{self.comum.id}/excluir'),
            ('post', '/api/admin/conteudo/cards'),
            ('put', f'/api/admin/conteudo/cards/{card.id}'),
            ('post', f'/api/admin/conteudo/cards/{card.id}/reordenar'),
        ]
        for metodo, url in rotas:
            resposta = self.bruto(metodo, url)
            self.assertEqual(resposta.status_code, 400, url)
            self.assertEqual(resposta.json()['mensagem'], 'JSON inválido.')
        self.assertTrue(Usuario.objects.get(pk=self.comum.pk).ativo)
        self.assertEqual(Card.objects.get(pk=card.pk).ordem, 1)
        self.assertEqual(self.bruto('post', '/api/admin/conteudo/cards', '[1, 2]').status_code, 400)

    def test_acao_desconhecida_responde_404(self):
        card = Card.objects.get(codigo='1.1')
        self.assertEqual(self.chamar('get', f'/api/admin/conteudo/cards/{card.id}/apagar').status_code, 404)
        self.assertEqual(self.chamar('post', f'/api/admin/conteudo/cards/{card.id}/impacto').status_code, 404)
        self.assertEqual(self.chamar('post', f'/api/admin/conteudo/cards/{card.id}/apagar_de_vez').status_code, 404)
        self.assertTrue(Card.objects.filter(pk=card.pk, excluido_em__isnull=True).exists())


class EntradasInvalidasDiarioTests(BaseAdminTests):
    def setUp(self):
        super().setUp()
        self.user = criar_usuario('diario@exemplo.com')
        for tipo in (*Consentimento.DOCUMENTOS, Consentimento.Tipo.SAUDE):
            Consentimento.objects.create(usuario=self.user, tipo=tipo, versao_documento='1.0', aceito=True)
        Usuario.objects.filter(pk=self.user.pk).update(situacao_menstrual='ja_menstruo')
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=self.user).chave}'}

    def test_json_invalido_no_diario(self):
        for metodo, url in (('put', '/api/diario/situacao'), ('put', '/api/diario/2026-01-10')):
            resposta = getattr(self.client, metodo)(url, '{x', content_type='application/json', **self.auth)
            self.assertEqual(resposta.status_code, 400, url)

    def test_termos_revogados_bloqueiam_o_diario_mas_nao_a_exclusao(self):
        Consentimento.objects.create(usuario=self.user, tipo=Consentimento.Tipo.TERMOS_USO, versao_documento='2.0', aceito=False)
        self.assertEqual(self.client.get('/api/diario', **self.auth).status_code, 403)
        self.assertEqual(self.client.get('/api/diario/resumo', **self.auth).status_code, 403)
        resposta = self.client.delete('/api/diario', {'confirmar': True}, content_type='application/json', **self.auth)
        self.assertEqual(resposta.status_code, 200)
