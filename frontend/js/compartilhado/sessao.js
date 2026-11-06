const API_SESSAO = 'http://127.0.0.1:8000/api';

function concluirLogin(resultado) {
  localStorage.setItem('flori_token', resultado.token);
  localStorage.setItem('flori_apelido', resultado.apelido);
  window.location.href = 'home.html';
}

function tokenDaSessao() {
  return localStorage.getItem('flori_token');
}

async function encerrarSessao() {
  const token = tokenDaSessao();
  if (token) {
    try {
      await fetch(`${API_SESSAO}/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
    }
  }
  localStorage.removeItem('flori_token');
  localStorage.removeItem('flori_apelido');
}
