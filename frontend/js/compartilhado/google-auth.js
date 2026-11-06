import { auth } from './firebase.js';
import {
  GoogleAuthProvider, signInWithPopup, signOut
} from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js';

export const CHAVE_CADASTRO_GOOGLE = 'flori_cadastro_google';

const provedor = new GoogleAuthProvider();
provedor.setCustomParameters({ prompt: 'select_account' });

const MENSAGENS_FIREBASE = {
  'auth/popup-blocked': 'O navegador bloqueou a janela do Google. Libere os pop-ups deste site e tente de novo.',
  'auth/unauthorized-domain': 'Este endereço ainda não está autorizado no Firebase. Veja "Domínios autorizados" no console.',
  'auth/operation-not-allowed': 'O login com Google ainda não foi ativado no Firebase.',
  'auth/configuration-not-found': 'O Firebase Authentication ainda não foi configurado neste projeto.',
  'auth/network-request-failed': 'Sem conexão com o Google. Confere sua internet.',
};

const DESISTENCIAS = ['auth/popup-closed-by-user', 'auth/cancelled-popup-request'];

export async function continuarComGoogle() {
  let idToken;
  try {
    const resultadoGoogle = await signInWithPopup(auth, provedor);
    idToken = await resultadoGoogle.user.getIdToken();
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
