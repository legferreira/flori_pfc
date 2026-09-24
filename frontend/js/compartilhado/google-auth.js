// Flori — "Continuar com Google" (módulo compartilhado por login e cadastro)
//
// 1. Abre o popup do Google pelo Firebase Authentication.
// 2. Pega o ID token (assinado pelo Google) e manda para POST /api/login/google.
// 3. O back-end verifica o token e responde:
//    - {token, ...}                  -> já tem conta: login concluído;
//    - {cadastro_necessario, email, nome, sobrenome} -> falta o cadastro.

import { auth } from './firebase.js';
import {
  GoogleAuthProvider, signInWithPopup, signOut
} from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js';

// Onde o login pela tela de login guarda o perfil Google para o cadastro continuar.
export const CHAVE_CADASTRO_GOOGLE = 'flori_cadastro_google';

const provedor = new GoogleAuthProvider();
// Sempre deixa escolher a conta, em vez de entrar direto na última usada.
provedor.setCustomParameters({ prompt: 'select_account' });

// Erros do Firebase que merecem mensagem própria (o resto cai na genérica).
const MENSAGENS_FIREBASE = {
  'auth/popup-blocked': 'O navegador bloqueou a janela do Google. Libere os pop-ups deste site e tente de novo.',
  'auth/unauthorized-domain': 'Este endereço ainda não está autorizado no Firebase. Veja "Domínios autorizados" no console.',
  'auth/operation-not-allowed': 'O login com Google ainda não foi ativado no Firebase.',
  // Authentication nunca foi iniciado no projeto (botão "Get started" no console).
  'auth/configuration-not-found': 'O Firebase Authentication ainda não foi configurado neste projeto.',
  'auth/network-request-failed': 'Sem conexão com o Google. Confere sua internet.',
};

// Quem fechou o popup ou clicou de novo só desistiu — não é erro para mostrar.
const DESISTENCIAS = ['auth/popup-closed-by-user', 'auth/cancelled-popup-request'];

// Devolve { status, resultado, idToken }, ou null se a pessoa fechou o popup.
// Lança Error com a mensagem pronta para exibir nos outros casos.
export async function continuarComGoogle() {
  let idToken;
  try {
    const resultadoGoogle = await signInWithPopup(auth, provedor);
    idToken = await resultadoGoogle.user.getIdToken();
    // A sessão que vale é a do Flori (token do back-end). A do Firebase só
    // serviu para provar quem é a pessoa — encerra para não ficar pendurada.
    await signOut(auth);
  } catch (erro) {
    if (DESISTENCIAS.includes(erro.code)) return null;
    throw new Error(MENSAGENS_FIREBASE[erro.code] || 'Não foi possível entrar com o Google. Tente de novo.');
  }

  let resposta;
  try {
    resposta = await fetch('http://127.0.0.1:8000/api/login/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: idToken })
    });
  } catch {
    throw new Error('Não foi possível conectar ao servidor. Confere se o back-end está rodando.');
  }
  return { status: resposta.status, resultado: await resposta.json(), idToken };
}
