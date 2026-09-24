// Flori — Lógica do formulário de login

// concluirLogin() vem de sessao.js (carregado antes deste arquivo).

const form = document.getElementById('formLogin');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  document.querySelectorAll('.flori-error').forEach(el => el.style.display = 'none');

  let valido = true;
  const contato = document.getElementById('contato').value.trim();
  const senha = document.getElementById('senha').value;

  if (!contato) {
    document.getElementById('erroContato').style.display = 'block';
    valido = false;
  }
  if (!senha) {
    document.getElementById('erroSenha').style.display = 'block';
    valido = false;
  }
  if (!valido) return;

  try {
    const resposta = await fetch('http://127.0.0.1:8000/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contato, senha })
    });

    const resultado = await resposta.json();

    if (resposta.status === 200 && resultado.requer_codigo) {
      // Senha certa, mas falta o código de 6 dígitos enviado por e-mail (2FA).
      // sessionStorage (não localStorage): o desafio só vale nesta aba e some
      // ao fechá-la — é um login pela metade, não deve ficar guardado.
      sessionStorage.setItem('flori_2fa', JSON.stringify({
        desafio: resultado.desafio,
        email: resultado.email_mascarado,
        expiraEm: Date.now() + resultado.validade_minutos * 60 * 1000,
      }));
      window.location.href = 'verificar-codigo.html';
    } else if (resposta.status === 200) {
      // Conta sem e-mail: login concluído direto, sem código.
      concluirLogin(resultado);
    } else {
      // Mensagem vinda do back-end ("Contato ou senha incorretos.", ou 503 se
      // o e-mail com o código não pôde ser enviado) exibida no campo de senha,
      // de propósito sem dizer se foi o contato ou a senha que errou.
      document.getElementById('erroSenha').textContent = resultado.mensagem;
      document.getElementById('erroSenha').style.display = 'block';
    }
  } catch (erro) {
    alert('Não foi possível conectar ao servidor. Confere se o back-end está rodando.');
  }
});