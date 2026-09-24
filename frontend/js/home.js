// Flori — Home (área logada): foto do Google + botão Sair
//
// Confirma a sessão com GET /api/perfil (token no header Authorization).
// Sem token, ou token que o servidor não reconhece mais: volta para o login.

import { auth } from './compartilhado/firebase.js';
import { signOut } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js';

const foto = document.getElementById('fotoUsuario');
const inicial = document.getElementById('inicialUsuario');

function mostrarInicial(apelido) {
  foto.hidden = true;
  inicial.textContent = (apelido || '?').trim().charAt(0).toUpperCase();
  inicial.hidden = false;
}

function mostrarPerfil(perfil) {
  document.getElementById('nomeUsuario').textContent = perfil.apelido;
  document.getElementById('saudacao').textContent = `Oi, ${perfil.apelido}!`;

  if (perfil.foto_url) {
    // Foto do Google fora do ar ou link expirado: cai para a inicial.
    foto.onerror = () => mostrarInicial(perfil.apelido);
    foto.src = perfil.foto_url;
    foto.alt = `Foto de ${perfil.apelido}`;
    foto.hidden = false;
  } else {
    mostrarInicial(perfil.apelido);
  }

  document.getElementById('topo').hidden = false;
  document.getElementById('conteudo').hidden = false;
}

async function carregar() {
  const token = tokenDaSessao(); // sessao.js
  if (!token) {
    window.location.replace('login.html');
    return;
  }

  let resposta;
  try {
    resposta = await fetch(`${API_SESSAO}/perfil`, { headers: { Authorization: `Bearer ${token}` } });
  } catch {
    // Servidor fora do ar: mostra com o que tem guardado em vez de deslogar.
    mostrarPerfil({ apelido: localStorage.getItem('flori_apelido') || '' });
    return;
  }

  if (resposta.status === 401) {
    // Token apagado no servidor (saiu em outro lugar, trocou a senha...).
    await encerrarSessao();
    window.location.replace('login.html');
    return;
  }
  mostrarPerfil(await resposta.json());
}

document.getElementById('botaoSair').addEventListener('click', async (e) => {
  e.currentTarget.disabled = true;
  await encerrarSessao(); // sessao.js — apaga o token no servidor e no navegador
  // Encerra também a sessão do Google no Firebase, se houver alguma aberta.
  try { await signOut(auth); } catch { /* nada a encerrar */ }
  window.location.replace('index.html');
});

carregar();
