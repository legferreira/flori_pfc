// Flori — Sessão (script comum, compartilhado pelas páginas que fazem login)

const API_SESSAO = 'http://127.0.0.1:8000/api';

// Última etapa de qualquer login (senha, código 2FA, Google, cadastro pelo
// Google): guarda o token no navegador — vai ser reenviado no header
// Authorization das requisições que precisam saber quem está logada —
// e leva para a home.
function concluirLogin(resultado) {
  localStorage.setItem('flori_token', resultado.token);
  localStorage.setItem('flori_apelido', resultado.apelido);
  window.location.href = 'home.html';
}

function tokenDaSessao() {
  return localStorage.getItem('flori_token');
}

// Sair: invalida o token no servidor (POST /api/logout apaga ele do banco)
// e só depois limpa o navegador. Mesmo se o servidor estiver fora do ar,
// limpa o navegador — a pessoa pediu para sair, não pode ficar "presa".
async function encerrarSessao() {
  const token = tokenDaSessao();
  if (token) {
    try {
      await fetch(`${API_SESSAO}/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      // Sem conexão: o token fica no banco até a próxima troca de senha.
    }
  }
  localStorage.removeItem('flori_token');
  localStorage.removeItem('flori_apelido');
}
