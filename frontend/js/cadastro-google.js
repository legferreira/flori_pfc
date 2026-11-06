import { continuarComGoogle, CHAVE_CADASTRO_GOOGLE } from './compartilhado/google-auth.js';

const botaoGoogle = document.getElementById('botaoGoogleCadastro');
const erroGoogle = document.getElementById('erroGoogle');

try {
  const pendente = JSON.parse(sessionStorage.getItem(CHAVE_CADASTRO_GOOGLE));
  if (pendente && pendente.idToken) ativarModoGoogle(pendente);
} catch {
}

botaoGoogle.addEventListener('click', async () => {
  erroGoogle.style.display = 'none';
  botaoGoogle.disabled = true;

  try {
    const retorno = await continuarComGoogle();
    if (retorno) {
      const { status, resultado, idToken } = retorno;
      if (status === 200 && resultado.cadastro_necessario) {
        const perfil = { ...resultado, idToken };
        sessionStorage.setItem(CHAVE_CADASTRO_GOOGLE, JSON.stringify(perfil));
        ativarModoGoogle(perfil);
      } else if (status === 200) {
        concluirLogin(resultado);
        return;
      } else {
        throw new Error(resultado.mensagem);
      }
    }
  } catch (erro) {
    erroGoogle.textContent = erro.message;
    erroGoogle.style.display = 'block';
  }

  botaoGoogle.disabled = false;
});
