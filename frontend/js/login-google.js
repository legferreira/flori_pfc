// Flori — Botão "Continuar com Google" da tela de login
//
// Já tem conta: entra. Não tem: guarda o perfil Google e manda para o
// cadastro, que pede só o que o Google não fornece (apelido, data de
// nascimento, termos) — ver cadastro-google.js.

import { continuarComGoogle, CHAVE_CADASTRO_GOOGLE } from './compartilhado/google-auth.js';

const botaoGoogle = document.getElementById('botaoGoogle');
const erroGoogle = document.getElementById('erroGoogle');

botaoGoogle.addEventListener('click', async () => {
  erroGoogle.style.display = 'none';
  botaoGoogle.disabled = true;

  try {
    const retorno = await continuarComGoogle();
    if (retorno) {
      const { status, resultado, idToken } = retorno;
      if (status === 200 && resultado.cadastro_necessario) {
        sessionStorage.setItem(CHAVE_CADASTRO_GOOGLE, JSON.stringify({ ...resultado, idToken }));
        window.location.href = 'cadastro.html';
        return;
      }
      if (status === 200) {
        concluirLogin(resultado); // sessao.js
        return;
      }
      throw new Error(resultado.mensagem);
    }
  } catch (erro) {
    erroGoogle.textContent = erro.message;
    erroGoogle.style.display = 'block';
  }

  botaoGoogle.disabled = false;
});
