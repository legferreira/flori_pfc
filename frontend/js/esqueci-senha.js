// Flori — Modal "Esqueci minha senha"
//
// Quem manda no intervalo de espera (2, 4, 8... minutos) é o back-end: ele
// devolve 'espera_segundos' em toda resposta. Aqui só guardamos esse prazo
// por e-mail no localStorage para mostrar a contagem regressiva no botão,
// inclusive se a página for recarregada.

(() => {
  const CHAVE_PRAZOS = 'flori_esqueci_senha_prazos';

  const modal = document.getElementById('modalEsqueciSenha');
  const formulario = document.getElementById('formEsqueciSenha');
  const campoEmail = document.getElementById('emailEsqueciSenha');
  const botaoEnviar = document.getElementById('enviarEsqueciSenha');
  const erro = document.getElementById('erroEsqueciSenha');
  const sucesso = document.getElementById('sucessoEsqueciSenha');

  let relogio = null;

  // --- Prazos de espera por e-mail (localStorage) -------------------------

  function lerPrazos() {
    try {
      return JSON.parse(localStorage.getItem(CHAVE_PRAZOS)) || {};
    } catch {
      return {};
    }
  }

  function salvarPrazo(email, segundos) {
    const prazos = lerPrazos();
    prazos[email] = Date.now() + segundos * 1000;
    try {
      localStorage.setItem(CHAVE_PRAZOS, JSON.stringify(prazos));
    } catch {
      // Sem localStorage (ex: aba anônima): a contagem só dura até recarregar.
    }
  }

  function segundosRestantes(email) {
    const prazo = lerPrazos()[email];
    return prazo ? Math.max(0, Math.ceil((prazo - Date.now()) / 1000)) : 0;
  }

  // --- Botão com contagem regressiva --------------------------------------

  function formatar(segundos) {
    const minutos = Math.floor(segundos / 60);
    const resto = String(segundos % 60).padStart(2, '0');
    return `${minutos}:${resto}`;
  }

  function atualizarBotao() {
    const restante = segundosRestantes(emailDigitado());
    if (restante > 0) {
      botaoEnviar.disabled = true;
      botaoEnviar.textContent = `Enviar novamente em ${formatar(restante)}`;
    } else {
      botaoEnviar.disabled = false;
      botaoEnviar.textContent = 'Enviar';
    }
  }

  function iniciarRelogio() {
    clearInterval(relogio);
    atualizarBotao();
    relogio = setInterval(atualizarBotao, 1000);
  }

  function emailDigitado() {
    return campoEmail.value.trim().toLowerCase();
  }

  function mostrar(elemento, texto) {
    elemento.textContent = texto;
    elemento.style.display = 'block';
  }

  function limparMensagens() {
    erro.style.display = 'none';
    sucesso.style.display = 'none';
  }

  // --- Abrir / fechar ------------------------------------------------------

  document.getElementById('abrirEsqueciSenha').addEventListener('click', (e) => {
    e.preventDefault();
    // Aproveita o que já foi digitado no login, se for um e-mail.
    const contatoLogin = document.getElementById('contato').value.trim();
    if (!campoEmail.value && contatoLogin.includes('@')) {
      campoEmail.value = contatoLogin;
    }
    limparMensagens();
    modal.showModal();
    iniciarRelogio();
  });

  document.getElementById('fecharEsqueciSenha').addEventListener('click', () => modal.close());

  // Clique no fundo escurecido (fora do conteúdo) também fecha.
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.close();
  });

  modal.addEventListener('close', () => clearInterval(relogio));

  campoEmail.addEventListener('input', () => {
    limparMensagens();
    atualizarBotao();
  });

  // --- Envio ---------------------------------------------------------------

  formulario.addEventListener('submit', async (e) => {
    e.preventDefault();
    limparMensagens();

    const email = emailDigitado();
    if (!campoEmail.checkValidity() || !email) {
      mostrar(erro, 'Informe um e-mail válido.');
      return;
    }
    if (segundosRestantes(email) > 0) return;

    botaoEnviar.disabled = true;
    botaoEnviar.textContent = 'Enviando...';

    try {
      const resposta = await fetch('http://127.0.0.1:8000/api/resetar-senha', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const resultado = await resposta.json();

      if (resultado.espera_segundos) {
        salvarPrazo(email, resultado.espera_segundos);
      }

      if (resposta.status === 200) {
        mostrar(sucesso, resultado.mensagem);
      } else {
        mostrar(erro, resultado.mensagem);
      }
    } catch (erroRede) {
      mostrar(erro, 'Não foi possível conectar ao servidor. Confere se o back-end está rodando.');
    }

    iniciarRelogio();
  });
})();
