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
        concluirLogin(resultado);
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
