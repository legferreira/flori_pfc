// Flori — Página de nova senha (aberta pelo link do e-mail de "Esqueci minha senha")

const TAMANHO_MINIMO_SENHA = 8;

const formRedefinir = document.getElementById('formRedefinirSenha');
const botaoSalvar = document.getElementById('salvarNovaSenha');
const erroGeral = document.getElementById('erroRedefinirSenha');

// O token chega na URL: redefinir-senha.html?token=...
const token = new URLSearchParams(window.location.search).get('token');

// Tira o token da barra de endereço (e do histórico) assim que é lido,
// para ele não ficar exposto na tela nem ser reaberto pelo "voltar".
if (token) {
  history.replaceState(null, '', window.location.pathname);
}

function linkInvalido() {
  formRedefinir.style.display = 'none';
  document.getElementById('avisoLinkInvalido').style.display = 'block';
}

if (!token) linkInvalido();

formRedefinir.addEventListener('submit', async (e) => {
  e.preventDefault();
  document.querySelectorAll('.flori-error').forEach(el => el.style.display = 'none');

  const senha = document.getElementById('novaSenha').value;
  const confirmacao = document.getElementById('confirmarNovaSenha').value;

  if (senha.length < TAMANHO_MINIMO_SENHA) {
    document.getElementById('erroNovaSenha').style.display = 'block';
    return;
  }
  if (senha !== confirmacao) {
    document.getElementById('erroConfirmarNovaSenha').style.display = 'block';
    return;
  }

  botaoSalvar.disabled = true;
  botaoSalvar.textContent = 'Salvando...';

  try {
    const resposta = await fetch('http://127.0.0.1:8000/api/resetar-senha/confirmar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, senha })
    });
    const resultado = await resposta.json();

    if (resposta.status === 200) {
      // As sessões antigas foram encerradas no back-end; limpa a daqui também.
      localStorage.removeItem('flori_token');
      localStorage.removeItem('flori_apelido');
      formRedefinir.style.display = 'none';
      document.getElementById('mensagemSucessoRedefinir').textContent = resultado.mensagem;
      document.getElementById('sucessoRedefinirSenha').style.display = 'block';
      return;
    }

    erroGeral.textContent = resultado.mensagem;
    erroGeral.style.display = 'block';
  } catch (erro) {
    erroGeral.textContent = 'Não foi possível conectar ao servidor. Confere se o back-end está rodando.';
    erroGeral.style.display = 'block';
  }

  botaoSalvar.disabled = false;
  botaoSalvar.textContent = 'Salvar nova senha';
});
