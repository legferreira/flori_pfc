// Flori — Lógica do formulário de login
// Estrutura pronta — a autenticação real entra quando o back-end do cadastro
// estiver validado e integrado. Por enquanto, só validação de campo vazio.

// Referência ao formulário de login
const form = document.getElementById('formLogin');

// Tratamento do envio do formulário: valida se os campos foram preenchidos
form.addEventListener('submit', (e) => {
  e.preventDefault(); // impede o recarregamento padrão da página

  // Esconde todas as mensagens de erro antes de revalidar
  document.querySelectorAll('.flori-error').forEach(el => el.style.display = 'none');

  let valido = true;

  // Validação: campo de contato (e-mail ou celular) não pode estar vazio
  if (!document.getElementById('contato').value.trim()) {
    document.getElementById('erroContato').style.display = 'block';
    valido = false;
  }

  // Validação: campo de senha não pode estar vazio
  if (!document.getElementById('senha').value) {
    document.getElementById('erroSenha').style.display = 'block';
    valido = false;
  }

  // Se algum campo for inválido, interrompe o envio (os erros já foram exibidos acima)
  if (!valido) return;

  // TODO: integrar com o endpoint de login quando o cadastro estiver validado.
  // Por enquanto, sem back-end conectado, apenas indica no console que passou na validação
  console.log('Login pronto para ser conectado ao back-end.');
});
