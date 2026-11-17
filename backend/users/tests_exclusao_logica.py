from datetime import timedelta
import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .models import CodigoAutenticacao, Consentimento, ExclusaoFisicaProibida, LogAtividade, Token, Usuario
from .services import ExcluirConta
from .tests_conta import SENHA, criar_usuario

CAMPOS_PESSOAIS = ('email', 'celular', 'foto_url')


@patch('users.services.NotificacaoService')
class ExclusaoLogicaTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(celular='(11) 91234-5678', foto_url='https://exemplo.com/foto.png')
        self.token = Token.objects.create(usuario=self.usuario)
        self.id_original = self.usuario.id

    def excluir(self):
        ExcluirConta(self.usuario.id).executar()
        self.usuario.refresh_from_db()

    def test_linha_fica_inativa_e_sem_dados_pessoais(self, notificacao):
        self.excluir()
        u = self.usuario
        self.assertFalse(u.ativo)
        self.assertIsNotNone(u.excluido_em)
        for campo in CAMPOS_PESSOAIS:
            self.assertIsNone(getattr(u, campo), campo)
        self.assertEqual((u.nome, u.sobrenome, u.apelido), ('Conta excluída',) * 3)
        self.assertEqual(u.data_nascimento, Usuario.NASCIMENTO_EXCLUIDO)
        self.assertFalse(u.tem_senha())
        self.assertFalse(u.verificar_senha(SENHA))
        self.assertEqual(Consentimento.objects.filter(usuario=u).count(), 2)

    def test_log_de_exclusao_guarda_id_real_e_nenhum_dado_pessoal(self, notificacao):
        self.excluir()
        log = LogAtividade.objects.get(acao=LogAtividade.Acao.EXCLUSAO_CONTA_PROPRIA)
        self.assertEqual(log.alvo_id, str(self.id_original))
        texto = json.dumps(list(LogAtividade.objects.values('resumo', 'alvo_id', 'alvo_tipo')))
        for dado in ('ana@exemplo.com', '91234', 'Souza'):
            self.assertNotIn(dado, texto)

    def test_email_original_fica_livre_para_novo_cadastro(self, notificacao):
        self.excluir()
        resposta = self.client.post('/api/usuarios', {
            'nome': 'Ana', 'sobrenome': 'Lima', 'data_nascimento': '1995-04-10', 'email': 'ana@exemplo.com',
            'celular': '(11) 91234-5678', 'senha': 'outra-senha-1', 'termos_aceitos': True,
        }, content_type='application/json')
        self.assertEqual(resposta.status_code, 201)
        novo = Usuario.objects.get(email='ana@exemplo.com')
        self.assertNotEqual(novo.id, self.id_original)
        self.assertTrue(novo.ativo)
        self.assertEqual(Usuario.objects.count(), 2)

    @patch('google.oauth2.id_token.verify_firebase_token')
    def test_login_google_com_email_antigo_pede_cadastro_novo(self, verificar, notificacao):
        verificar.return_value = {
            'email': 'ana@exemplo.com', 'email_verified': True, 'name': 'Ana Souza',
            'firebase': {'sign_in_provider': 'google.com'},
        }
        self.excluir()
        resposta = self.client.post('/api/login/google', {'id_token': 't'}, content_type='application/json')
        self.assertTrue(resposta.json()['cadastro_necessario'])
        cadastro = self.client.post('/api/usuarios/google', {
            'id_token': 't', 'nome': 'Ana', 'sobrenome': 'Souza', 'data_nascimento': '1995-04-10', 'termos_aceitos': True,
        }, content_type='application/json')
        self.assertEqual(cadastro.status_code, 201)
        self.assertNotEqual(Usuario.objects.get(email='ana@exemplo.com').id, self.id_original)

    def test_conta_inativa_nao_loga_e_recebe_mensagem_generica(self, notificacao):
        self.excluir()
        resposta = self.client.post(
            '/api/login', {'contato': 'ana@exemplo.com', 'senha': SENHA}, content_type='application/json',
        )
        inexistente = self.client.post(
            '/api/login', {'contato': 'ninguem@exemplo.com', 'senha': SENHA}, content_type='application/json',
        )
        self.assertEqual(resposta.status_code, 401)
        self.assertEqual(resposta.json(), inexistente.json())
        notificacao.return_value.enviar_codigo_autenticacao.assert_not_called()

    def test_conta_inativa_nao_passa_pelo_2fa(self, notificacao):
        self.excluir()
        desafio = 'desafio-de-teste'
        registro = CodigoAutenticacao(
            usuario=self.usuario, desafio_hash=CodigoAutenticacao.gerar_hash_desafio(desafio),
            expira_em=timezone.now() + timedelta(minutes=10),
        )
        registro.definir_codigo('123456')
        registro.save()
        resposta = self.client.post(
            '/api/login/verificar', {'desafio': desafio, 'codigo': '123456'}, content_type='application/json',
        )
        self.assertEqual(resposta.status_code, 410)
        self.assertFalse(Token.objects.filter(usuario=self.usuario).exists())

    def test_token_de_conta_inativa_nao_vale(self, notificacao):
        Usuario.objects.filter(pk=self.usuario.pk).update(ativo=False)
        resposta = self.client.get('/api/perfil', HTTP_AUTHORIZATION=f'Bearer {self.token.chave}')
        self.assertEqual(resposta.status_code, 401)

    def test_redefinicao_de_senha_nao_alcanca_conta_inativa(self, notificacao):
        self.excluir()
        self.client.post('/api/resetar-senha', {'email': 'ana@exemplo.com'}, content_type='application/json')
        notificacao.return_value.enviar_recuperacao_senha.assert_not_called()

    def test_delete_fisico_de_conta_comum_e_bloqueado(self, notificacao):
        with self.assertRaises(ExclusaoFisicaProibida):
            self.usuario.delete()
        with self.assertRaises(ExclusaoFisicaProibida):
            Usuario.objects.filter(pk=self.usuario.pk).delete()
        with self.assertRaises(ExclusaoFisicaProibida):
            Usuario.objects.filter(pk=self.usuario.pk).apagar_demo_definitivo()
        self.assertTrue(Usuario.objects.filter(pk=self.usuario.pk).exists())
