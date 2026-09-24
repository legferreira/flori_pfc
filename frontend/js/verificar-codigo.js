// Flori — Verificação do código de 2 fatores (segunda etapa do login)
//
// login.js guarda em sessionStorage ('flori_2fa') o desafio devolvido pelo
// back-end, o e-mail mascarado e a hora em que o código expira. Esta página
// manda desafio + código digitado para POST /api/login/verificar.

const CHAVE_2FA = 'flori_2fa';

const formVerificar = document.getElementById('formVerificarCodigo');
const campoCodigo = document.getElementById('codigo');
const botaoVerificar = document.getElementById('botaoVerificar');
const erroCodigo = document.getElementById('erroCodigo');
const validadeCodigo = document.getElementById('validadeCodigo');

let relogio = null;

function lerLoginPendente() {
  try {
    return JSON.parse(sessionStorage.getItem(CHAVE_2FA));
  } catch {
    return null;
  }
}

const pendente = lerLoginPendente();

// Troca o formulário pelo aviso de "faça login de novo" e descarta o desafio.
function encerrar(mensagem) {
  clearInterval(relogio);
  sessionStorage.removeItem(CHAVE_2FA);
  if (mensagem) document.getElementById('mensagemExpirado').textContent = mensagem;
  formVerificar.hidden = true;
  document.getElementById('codigoExpirado').hidden = false;
}

// Contagem regressiva só informativa — quem decide se expirou é o back-end.
function atualizarValidade() {
  const restante = Math.ceil((pendente.expiraEm - Date.now()) / 1000);
  if (restante <= 0) {
    encerrar('Este código expirou. Faça login de novo para receber um novo código.');
    return;
  }
  const minutos = Math.floor(restante / 60);
  const segundos = String(restante % 60).padStart(2, '0');
  validadeCodigo.textContent = `O código expira em ${minutos}:${segundos}.`;
}

if (!pendente || !pendente.desafio) {
  // Página aberta direto (sem passar pelo login) ou aba recarregada depois de fechar.
  encerrar('Para receber um código, faça login primeiro.');
} else {
  document.getElementById('emailMascarado').textContent = pendente.email;
  atualizarValidade();
  relogio = setInterval(atualizarValidade, 1000);
  campoCodigo.focus();
}

// Aceita só números (inclusive ao colar "123 456" ou "123-456").
campoCodigo.addEventListener('input', () => {
  campoCodigo.value = campoCodigo.value.replace(/\D/g, '').slice(0, 6);
  erroCodigo.style.display = 'none';
});

formVerificar.addEventListener('submit', async (e) => {
  e.preventDefault();
  erroCodigo.style.display = 'none';

  const codigo = campoCodigo.value;
  if (codigo.length !== 6) {
    erroCodigo.textContent = 'Digite os 6 números do código.';
    erroCodigo.style.display = 'block';
    return;
  }

  botaoVerificar.disabled = true;
  botaoVerificar.textContent = 'Verificando...';

  try {
    const resposta = await fetch('http://127.0.0.1:8000/api/login/verificar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ desafio: pendente.desafio, codigo })
    });
    const resultado = await resposta.json();

    if (resposta.status === 200) {
      sessionStorage.removeItem(CHAVE_2FA);
      concluirLogin(resultado); // sessao.js
      return;
    }
    if (resposta.status === 410) {
      // Expirou ou errou demais: este desafio não serve mais.
      encerrar(resultado.mensagem);
      return;
    }
    // 400: "Código inválido. Tente novamente."
    erroCodigo.textContent = resultado.mensagem;
    erroCodigo.style.display = 'block';
    campoCodigo.select();
  } catch (erro) {
    erroCodigo.textContent = 'Não foi possível conectar ao servidor. Confere se o back-end está rodando.';
    erroCodigo.style.display = 'block';
  }

  botaoVerificar.disabled = false;
  botaoVerificar.textContent = 'Verificar e entrar';
});
