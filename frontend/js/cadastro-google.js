// Flori — "Continuar com Google" no passo 2 do cadastro
//
// Já existe conta com esse e-mail do Google: entra direto.
// Não existe: liga o modo Google do cadastro (ativarModoGoogle, em
// cadastro.js) — passo 3 só com os termos, sem senha.

import { continuarComGoogle, CHAVE_CADASTRO_GOOGLE } from './compartilhado/google-auth.js';

const botaoGoogle = document.getElementById('botaoGoogleCadastro');
const erroGoogle = document.getElementById('erroGoogle');

// Veio da tela de login ("Continuar com Google" sem conta): retoma com o
// perfil Google que ela guardou. O passo 1 ainda precisa ser preenchido.
try {
  const pendente = JSON.parse(sessionStorage.getItem(CHAVE_CADASTRO_GOOGLE));
  if (pendente && pendente.idToken) ativarModoGoogle(pendente);
} catch {
  // sessionStorage indisponível ou valor corrompido: segue o cadastro normal.
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
        ativarModoGoogle(perfil); // cadastro.js
      } else if (status === 200) {
        concluirLogin(resultado); // já tinha conta — sessao.js
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
