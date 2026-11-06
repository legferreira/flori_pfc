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
      sessionStorage.setItem('flori_2fa', JSON.stringify({
        desafio: resultado.desafio,
        email: resultado.email_mascarado,
        expiraEm: Date.now() + resultado.validade_minutos * 60 * 1000,
      }));
      window.location.href = 'verificar-codigo.html';
    } else if (resposta.status === 200) {
      concluirLogin(resultado);
    } else {
      document.getElementById('erroSenha').textContent = resultado.mensagem;
      document.getElementById('erroSenha').style.display = 'block';
    }
  } catch (erro) {
    alert('Não foi possível conectar ao servidor. Confere se o back-end está rodando.');
  }
});
