from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .models import CodigoAutenticacao, Consentimento, LogAtividade, SolicitacaoRedefinicaoSenha, Token, Usuario


def criar_usuario(senha='senha12345', **extra):
    usuario = Usuario(
        nome='Ana', sobrenome='Souza', apelido='ana',
        data_nascimento='10/04/1995', email='ana@exemplo.com', **extra,
    )
    usuario.definir_senha(senha)
    usuario.save()
    return usuario


@patch('users.services.NotificacaoService')
class ResetarSenhaTests(TestCase):
    URL = '/api/resetar-senha'

    def setUp(self):
        self.usuario = criar_usuario()

    def pedir(self, email='ana@exemplo.com'):
        return self.client.post(self.URL, {'email': email}, content_type='application/json')

    def envelhecer_pedidos(self, minutos):
        for pedido in SolicitacaoRedefinicaoSenha.objects.all():
            pedido.criado_em -= timedelta(minutes=minutos)
            pedido.save(update_fields=['criado_em'])

    def test_envia_email_com_token_e_guarda_so_o_hash(self, notificacao):
        resposta = self.pedir()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['espera_segundos'], 2 * 60)
        link = notificacao.return_value.enviar_recuperacao_senha.call_args.args[1]
        token = link.split('token=')[1]
        pedido = SolicitacaoRedefinicaoSenha.objects.get()
        self.assertEqual(pedido.usuario, self.usuario)
        self.assertEqual(pedido.token_hash, SolicitacaoRedefinicaoSenha.gerar_hash(token))
        self.assertNotIn(token, pedido.token_hash)
        self.assertGreater(pedido.expira_em, timezone.now())

    def test_espera_dobra_a_cada_pedido(self, notificacao):
        self.assertEqual(self.pedir().status_code, 200)

        bloqueado = self.pedir()
        self.assertEqual(bloqueado.status_code, 429)
        self.assertGreater(bloqueado.json()['espera_segundos'], 0)

        self.envelhecer_pedidos(2)
        segundo = self.pedir()
        self.assertEqual(segundo.status_code, 200)
        self.assertEqual(segundo.json()['espera_segundos'], 4 * 60)

        self.envelhecer_pedidos(3)
        self.assertEqual(self.pedir().status_code, 429)

        self.envelhecer_pedidos(1)
        terceiro = self.pedir()
        self.assertEqual(terceiro.status_code, 200)
        self.assertEqual(terceiro.json()['espera_segundos'], 8 * 60)

    def test_contagem_zera_depois_de_24h_sem_pedidos(self, notificacao):
        self.pedir()
        self.envelhecer_pedidos(2)
        self.pedir()
        self.envelhecer_pedidos(24 * 60 + 1)

        resposta = self.pedir()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['espera_segundos'], 2 * 60)

    def test_email_inexistente_responde_igual_e_nao_envia(self, notificacao):
        cadastrado = self.pedir()
        inexistente = self.pedir('ninguem@exemplo.com')

        self.assertEqual(inexistente.status_code, 200)
        self.assertEqual(inexistente.json(), cadastrado.json())
        self.assertEqual(notificacao.return_value.enviar_recuperacao_senha.call_count, 1)
        self.assertEqual(self.pedir('ninguem@exemplo.com').status_code, 429)

    def test_email_invalido(self, notificacao):
        self.assertEqual(self.pedir('nao-e-email').status_code, 400)

    def test_email_maior_que_a_coluna(self, notificacao):
        self.assertEqual(self.pedir('a' * 150 + '@exemplo.com').status_code, 400)
        self.assertFalse(SolicitacaoRedefinicaoSenha.objects.exists())

    def test_falha_no_envio_nao_derruba_o_pedido(self, notificacao):
        notificacao.return_value.enviar_recuperacao_senha.side_effect = Exception('Brevo fora')
        self.assertEqual(self.pedir().status_code, 200)


@patch('users.services.NotificacaoService')
class ConfirmarResetarSenhaTests(TestCase):
    URL = '/api/resetar-senha/confirmar'

    def setUp(self):
        self.usuario = criar_usuario(senha='senha-antiga')

    def gerar_token(self, notificacao):
        self.client.post(
            '/api/resetar-senha', {'email': 'ana@exemplo.com'}, content_type='application/json',
        )
        link = notificacao.return_value.enviar_recuperacao_senha.call_args.args[1]
        return link.split('token=')[1]

    def confirmar(self, token, senha='senha-nova-123'):
        return self.client.post(
            self.URL, {'token': token, 'senha': senha}, content_type='application/json',
        )

    def test_troca_a_senha_e_encerra_sessoes(self, notificacao):
        Token.objects.create(usuario=self.usuario)
        token = self.gerar_token(notificacao)

        resposta = self.confirmar(token)

        self.assertEqual(resposta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.verificar_senha('senha-nova-123'))
        self.assertFalse(Token.objects.filter(usuario=self.usuario).exists())
        self.assertTrue(LogAtividade.objects.filter(
            usuario=self.usuario, acao=LogAtividade.Acao.SENHA_REDEFINIDA,
        ).exists())

    def test_token_so_vale_uma_vez(self, notificacao):
        token = self.gerar_token(notificacao)
        self.assertEqual(self.confirmar(token).status_code, 200)
        self.assertEqual(self.confirmar(token, 'outra-senha-456').status_code, 400)

    def test_token_expirado(self, notificacao):
        token = self.gerar_token(notificacao)
        SolicitacaoRedefinicaoSenha.objects.update(expira_em=timezone.now() - timedelta(seconds=1))

        self.assertEqual(self.confirmar(token).status_code, 400)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.verificar_senha('senha-antiga'))

    def test_token_inexistente(self, notificacao):
        self.assertEqual(self.confirmar('token-inventado').status_code, 400)

    def test_senha_curta_nao_gasta_o_token(self, notificacao):
        token = self.gerar_token(notificacao)
        self.assertEqual(self.confirmar(token, 'curta').status_code, 400)
        self.assertEqual(self.confirmar(token).status_code, 200)


@patch('users.services.NotificacaoService')
class LoginDoisFatoresTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()

    def login(self, contato='ana@exemplo.com', senha='senha12345'):
        return self.client.post(
            '/api/login', {'contato': contato, 'senha': senha}, content_type='application/json',
        )

    def verificar(self, desafio, codigo):
        return self.client.post(
            '/api/login/verificar', {'desafio': desafio, 'codigo': codigo},
            content_type='application/json',
        )

    def codigo_enviado(self, notificacao):
        return notificacao.return_value.enviar_codigo_autenticacao.call_args.args[1]

    def test_senha_certa_envia_codigo_e_nao_emite_token(self, notificacao):
        resposta = self.login()

        dados = resposta.json()
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(dados['requer_codigo'])
        self.assertNotIn('token', dados)
        self.assertEqual(dados['email_mascarado'], 'an*@exemplo.com')
        self.assertFalse(Token.objects.exists())
        codigo = self.codigo_enviado(notificacao)
        self.assertRegex(codigo, r'^\d{6}$')
        registro = CodigoAutenticacao.objects.get()
        self.assertNotIn(codigo, registro.codigo_hash)
        self.assertAlmostEqual(
            (registro.expira_em - registro.criado_em).total_seconds(), 15 * 60, delta=5,
        )

    def test_codigo_certo_conclui_login(self, notificacao):
        desafio = self.login().json()['desafio']

        resposta = self.verificar(desafio, self.codigo_enviado(notificacao))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['token'], Token.objects.get(usuario=self.usuario).chave)
        self.assertEqual(self.verificar(desafio, self.codigo_enviado(notificacao)).status_code, 410)

    def test_codigo_errado_permite_tentar_de_novo(self, notificacao):
        desafio = self.login().json()['desafio']
        codigo = self.codigo_enviado(notificacao)
        errado = '000000' if codigo != '000000' else '111111'

        resposta = self.verificar(desafio, errado)

        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(resposta.json()['mensagem'], 'Código inválido. Tente novamente.')
        self.assertEqual(self.verificar(desafio, codigo).status_code, 200)

    def test_bloqueia_depois_de_5_erros(self, notificacao):
        desafio = self.login().json()['desafio']
        codigo = self.codigo_enviado(notificacao)
        errado = '000000' if codigo != '000000' else '111111'

        respostas = [self.verificar(desafio, errado).status_code for _ in range(5)]

        self.assertEqual(respostas, [400, 400, 400, 400, 410])
        self.assertEqual(self.verificar(desafio, codigo).status_code, 410)
        self.assertFalse(Token.objects.exists())

    def test_codigo_expira_em_15_minutos(self, notificacao):
        desafio = self.login().json()['desafio']
        CodigoAutenticacao.objects.update(expira_em=timezone.now() - timedelta(seconds=1))

        self.assertEqual(self.verificar(desafio, self.codigo_enviado(notificacao)).status_code, 410)

    def test_novo_login_invalida_codigo_anterior(self, notificacao):
        desafio_antigo = self.login().json()['desafio']
        codigo_antigo = self.codigo_enviado(notificacao)
        self.login()

        self.assertEqual(self.verificar(desafio_antigo, codigo_antigo).status_code, 410)

    def test_senha_errada_nao_envia_codigo(self, notificacao):
        self.assertEqual(self.login(senha='errada').status_code, 401)
        notificacao.return_value.enviar_codigo_autenticacao.assert_not_called()

    def test_falha_no_envio_do_codigo_avisa(self, notificacao):
        notificacao.return_value.enviar_codigo_autenticacao.side_effect = Exception('Brevo fora')
        self.assertEqual(self.login().status_code, 503)

    def test_conta_sem_email_entra_direto(self, notificacao):
        self.usuario.email = None
        self.usuario.celular = '11900000000'
        self.usuario.save()

        resposta = self.login(contato='11900000000')

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.json()['requer_codigo'])
        self.assertIn('token', resposta.json())


@patch('google.oauth2.id_token.verify_firebase_token')
class LoginGoogleTests(TestCase):
    URL = '/api/login/google'

    def setUp(self):
        self.usuario = criar_usuario()

    def dados_google(self, **extra):
        return {
            'email': 'Ana@Exemplo.com', 'email_verified': True,
            'firebase': {'sign_in_provider': 'google.com'}, **extra,
        }

    def entrar(self, id_token='token-do-google'):
        return self.client.post(self.URL, {'id_token': id_token}, content_type='application/json')

    def test_conta_existente_entra_sem_codigo(self, verificar):
        verificar.return_value = self.dados_google()

        resposta = self.entrar()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['token'], Token.objects.get(usuario=self.usuario).chave)
        self.assertEqual(verificar.call_args.kwargs['audience'], 'flori-1742a')
        self.assertTrue(LogAtividade.objects.filter(acao=LogAtividade.Acao.LOGIN_GOOGLE).exists())

    def test_email_sem_conta_pede_cadastro(self, verificar):
        verificar.return_value = self.dados_google(email='outra@exemplo.com', name='Bia Lima Costa')

        resposta = self.entrar()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {
            'cadastro_necessario': True, 'email': 'outra@exemplo.com',
            'nome': 'Bia', 'sobrenome': 'Lima Costa', 'foto': None,
        })
        self.assertFalse(Token.objects.exists())

    def test_login_google_guarda_a_foto(self, verificar):
        verificar.return_value = self.dados_google(picture='https://lh3.googleusercontent.com/a/foto')

        self.entrar()

        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.foto_url, 'https://lh3.googleusercontent.com/a/foto')

    def test_token_invalido(self, verificar):
        verificar.side_effect = ValueError('assinatura inválida')
        self.assertEqual(self.entrar().status_code, 401)

    def test_email_nao_verificado(self, verificar):
        verificar.return_value = self.dados_google(email_verified=False)
        self.assertEqual(self.entrar().status_code, 401)

    def test_outro_provedor(self, verificar):
        verificar.return_value = self.dados_google(firebase={'sign_in_provider': 'password'})
        self.assertEqual(self.entrar().status_code, 401)

    def test_sem_token(self, verificar):
        self.assertEqual(self.entrar('').status_code, 400)
        verificar.assert_not_called()


@patch('users.services.NotificacaoService')
@patch('google.oauth2.id_token.verify_firebase_token')
class CadastroGoogleTests(TestCase):
    URL = '/api/usuarios/google'

    def setUp(self):
        self.dados = {
            'id_token': 'token-do-google', 'nome': 'Bia', 'sobrenome': 'Lima',
            'apelido': 'bia', 'data_nascimento': '2000-01-15', 'termos_aceitos': True,
        }

    def google(self, verificar, **extra):
        verificar.return_value = {
            'email': 'Bia@Gmail.com', 'email_verified': True, 'name': 'Bia Lima',
            'firebase': {'sign_in_provider': 'google.com'}, **extra,
        }

    def cadastrar(self, **extra):
        return self.client.post(self.URL, {**self.dados, **extra}, content_type='application/json')

    def test_cria_conta_sem_senha_entra_e_manda_boas_vindas(self, verificar, notificacao):
        self.google(verificar)

        resposta = self.cadastrar()

        self.assertEqual(resposta.status_code, 201)
        usuario = Usuario.objects.get()
        self.assertEqual(usuario.email, 'bia@gmail.com')
        self.assertEqual(usuario.data_nascimento, '15/01/2000')
        self.assertEqual(resposta.json()['token'], Token.objects.get(usuario=usuario).chave)
        self.assertEqual(usuario.consentimentos.count(), 2)
        self.assertFalse(usuario.verificar_senha(''))
        self.assertFalse(usuario.verificar_senha('None'))
        notificacao.return_value.enviar_confirmacao_cadastro.assert_called_once_with(usuario, via_google=True)

    def test_email_vem_do_google_e_nao_do_front(self, verificar, notificacao):
        self.google(verificar)
        self.cadastrar(email='outra-pessoa@exemplo.com')
        self.assertEqual(Usuario.objects.get().email, 'bia@gmail.com')

    def test_idade_minima_continua_valendo(self, verificar, notificacao):
        self.google(verificar)
        resposta = self.cadastrar(data_nascimento=timezone.now().date().replace(year=timezone.now().year - 10).isoformat())
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(Usuario.objects.exists())

    def test_termos_obrigatorios(self, verificar, notificacao):
        self.google(verificar)
        self.assertEqual(self.cadastrar(termos_aceitos=False).status_code, 400)

    def test_token_google_expirado(self, verificar, notificacao):
        verificar.side_effect = ValueError('expirado')
        self.assertEqual(self.cadastrar().status_code, 401)
        self.assertFalse(Usuario.objects.exists())

    def test_email_ja_cadastrado(self, verificar, notificacao):
        self.google(verificar)
        self.cadastrar()
        self.assertEqual(self.cadastrar(apelido='outra').status_code, 409)


@patch('users.services.NotificacaoService')
class CadastroNoMySQLTests(TestCase):
    URL = '/api/usuarios'

    def cadastrar(self, **extra):
        dados = {
            'nome': 'Bia', 'sobrenome': 'Lima', 'data_nascimento': '2000-01-15',
            'email': 'bia@exemplo.com', 'senha': 'senha12345', 'termos_aceitos': True,
        }
        return self.client.post(self.URL, {**dados, **extra}, content_type='application/json')

    def test_nome_longo_sem_apelido_cabe_na_coluna_do_apelido(self, notificacao):
        self.assertEqual(self.cadastrar(nome='A' * 80).status_code, 201)
        self.assertEqual(Usuario.objects.get().apelido, 'A' + 'a' * 49)

    def test_email_maior_que_a_coluna(self, notificacao):
        self.assertEqual(self.cadastrar(email='a' * 150 + '@exemplo.com').status_code, 400)

    def test_celular_maior_que_a_coluna(self, notificacao):
        self.assertEqual(self.cadastrar(celular='1' * 25).status_code, 400)

    def test_emoji_no_apelido(self, notificacao):
        self.assertEqual(self.cadastrar(apelido='Bia 🌸').status_code, 201)
        self.assertEqual(Usuario.objects.get().apelido, 'Bia 🌸')

    def test_email_com_acento_e_outra_conta(self, notificacao):
        self.assertEqual(self.cadastrar(email='joão@exemplo.com').status_code, 201)
        self.assertFalse(Usuario.objects.filter(email='joao@exemplo.com').exists())
        self.assertEqual(self.cadastrar(email='joao@exemplo.com').status_code, 201)


class SessaoTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(foto_url='https://lh3.googleusercontent.com/a/foto')
        self.token = Token.objects.create(usuario=self.usuario)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {self.token.chave}'}

    def test_perfil_traz_a_foto(self):
        resposta = self.client.get('/api/perfil', **self.auth)
        self.assertEqual(resposta.json()['foto_url'], 'https://lh3.googleusercontent.com/a/foto')

    def test_logout_apaga_o_token(self):
        resposta = self.client.post('/api/logout', **self.auth)

        self.assertEqual(resposta.status_code, 204)
        self.assertFalse(Token.objects.exists())
        self.assertEqual(self.client.get('/api/perfil', **self.auth).status_code, 401)
        self.assertTrue(LogAtividade.objects.filter(acao=LogAtividade.Acao.LOGOUT).exists())

    def test_logout_sem_token(self):
        self.assertEqual(self.client.post('/api/logout').status_code, 204)
        self.assertTrue(Token.objects.exists())


class PerfilTests(TestCase):
    def setUp(self):
        self.usuario = Usuario(
            nome='Ana', sobrenome='Souza', apelido='ana', data_nascimento='10/04/1995',
            email='ana@exemplo.com', celular='11 90000-0001',
        )
        self.usuario.definir_senha('senha12345')
        self.usuario.save()
        for tipo in Consentimento.Tipo.values:
            Consentimento.objects.create(usuario=self.usuario, tipo=tipo, versao_documento='1.0', aceito=True)
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {Token.objects.create(usuario=self.usuario).chave}'}

    def corrigir(self, dados):
        return self.client.patch('/api/perfil', dados, content_type='application/json', **self.auth)

    def revogar(self, tipo, aceito):
        return self.client.post(
            '/api/perfil/consentimentos', {'tipo': tipo, 'aceito': aceito},
            content_type='application/json', **self.auth,
        )

    def test_perfil_traz_dados_e_consentimentos(self):
        corpo = self.client.get('/api/perfil', **self.auth).json()
        self.assertEqual(corpo['sobrenome'], 'Souza')
        self.assertEqual(corpo['data_nascimento'], '10/04/1995')
        self.assertEqual(len(corpo['consentimentos']), 2)
        self.assertTrue(all(c['aceito'] for c in corpo['consentimentos']))

    def test_perfil_exige_token(self):
        self.assertEqual(self.client.patch('/api/perfil', {}, content_type='application/json').status_code, 401)
        self.assertEqual(self.client.post('/api/perfil/consentimentos').status_code, 401)

    def test_corrige_nome_apelido_e_celular(self):
        resposta = self.corrigir({'nome': 'maria  clara', 'apelido': 'mari', 'celular': '(11) 98888-7777'})
        self.assertEqual(resposta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertEqual((self.usuario.nome, self.usuario.apelido), ('Maria Clara', 'mari'))
        self.assertEqual(self.usuario.celular, '(11) 98888-7777')

    def test_so_atualiza_os_campos_enviados(self):
        self.corrigir({'apelido': 'aninha'})
        self.usuario.refresh_from_db()
        self.assertEqual((self.usuario.nome, self.usuario.celular), ('Ana', '11 90000-0001'))

    def test_apelido_vazio_volta_para_o_nome(self):
        self.corrigir({'apelido': ''})
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.apelido, 'Ana')

    def test_validacoes(self):
        self.assertEqual(self.corrigir({'nome': '  '}).status_code, 400)
        self.assertEqual(self.corrigir({'sobrenome': 'x' * 101}).status_code, 400)
        self.assertEqual(self.corrigir({'apelido': 'x' * 51}).status_code, 400)
        self.assertEqual(self.corrigir({'celular': '123'}).status_code, 400)

    def test_celular_de_outra_conta_recusado(self):
        outra = Usuario(nome='Bia', sobrenome='Lima', apelido='bia', data_nascimento='01/01/2000',
                        email='bia@exemplo.com', celular='11 97777-0000')
        outra.definir_senha('senha12345')
        outra.save()
        self.assertEqual(self.corrigir({'celular': '11 97777-0000'}).status_code, 409)

    def test_email_e_nascimento_nao_mudam(self):
        self.corrigir({'email': 'outro@exemplo.com', 'data_nascimento': '01/01/2015'})
        self.usuario.refresh_from_db()
        self.assertEqual((self.usuario.email, self.usuario.data_nascimento), ('ana@exemplo.com', '10/04/1995'))

    def test_revogar_cria_novo_registro_sem_apagar_o_anterior(self):
        resposta = self.revogar('termos_uso', False)
        self.assertEqual(resposta.status_code, 200)
        registros = Consentimento.objects.filter(usuario=self.usuario, tipo='termos_uso')
        self.assertEqual(registros.count(), 2)
        self.assertEqual([r.aceito for r in registros.order_by('data_consentimento')], [True, False])
        self.assertTrue(self.usuario.tem_consentimento_revogado())

    def test_revogado_bloqueia_a_trilha_mas_nao_o_perfil(self):
        self.revogar('politica_privacidade', False)
        self.assertEqual(self.client.get('/api/trilha', **self.auth).status_code, 403)
        self.assertEqual(self.client.get('/api/dashboard', **self.auth).status_code, 403)
        self.assertEqual(self.client.get('/api/perfil', **self.auth).status_code, 200)

    def test_reativar_libera_de_novo(self):
        self.revogar('politica_privacidade', False)
        self.revogar('politica_privacidade', True)
        self.assertFalse(Usuario.objects.get(pk=self.usuario.pk).tem_consentimento_revogado())
        self.assertEqual(Consentimento.objects.filter(usuario=self.usuario, tipo='politica_privacidade').count(), 3)

    def test_consentimento_invalido(self):
        self.assertEqual(self.revogar('inexistente', False).status_code, 400)
        self.assertEqual(self.revogar('termos_uso', 'sim').status_code, 400)

    def test_repetir_o_mesmo_estado_nao_duplica(self):
        self.revogar('termos_uso', True)
        self.assertEqual(Consentimento.objects.filter(usuario=self.usuario, tipo='termos_uso').count(), 1)
