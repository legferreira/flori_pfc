// Flori — Lógica do formulário de cadastro
// Regra de negócio: verificação de idade mínima (13 anos)

// --- Referências aos elementos do DOM (cadastro.html) --------------------
// document.getElementById busca o elemento HTML pelo atributo id="..." e
// guarda a referência numa constante, para não precisar buscar de novo toda hora.
const form = document.getElementById('formCadastro');         // <form id="formCadastro"> inteiro
const campoData = document.getElementById('dataNascimento');  // <input id="dataNascimento" type="date">
const blocoIdade = document.getElementById('blocoIdade');     // <div id="blocoIdade"> (aviso de idade insuficiente)
const erroIdade = document.getElementById('erroIdade');       // <div id="erroIdade"> (mensagem de erro no submit)
const campoSenha = document.getElementById('senha');          // <input id="senha" type="password">
const barraForca = document.getElementById('barraForca');     // <div id="barraForca"> (preenchimento da barra de força)

// Constante local, espelha Usuario.IDADE_MINIMA em backend/users/models.py.
// Duplicada de propósito: o front-end só usa isso para feedback visual (UX);
// quem garante a regra de verdade é sempre o back-end (ver comentário abaixo).
const IDADE_MINIMA = 13;

// Função declarada no escopo do módulo (não é método de objeto, é uma função
// solta), reaproveitada tanto no listener de 'change' quanto no de 'submit' abaixo.
// Recebe uma string de data (ex: '2010-05-20', formato do <input type="date">)
// e devolve a idade em anos completos, como número inteiro.
function calcularIdade(dataNascStr) {
  const hoje = new Date();                 // instancia um objeto Date com a data/hora atual
  const nascimento = new Date(dataNascStr); // instancia um Date a partir da string recebida
  let idade = hoje.getFullYear() - nascimento.getFullYear(); // diferença bruta de anos
  // Verifica se o aniversário deste ano ainda não chegou (mês menor,
  // ou mesmo mês com dia menor) — se sim, a pessoa ainda não completou o ano.
  const aindaNaoFezAniversario =
    hoje.getMonth() < nascimento.getMonth() ||
    (hoje.getMonth() === nascimento.getMonth() && hoje.getDate() < nascimento.getDate());
  if (aindaNaoFezAniversario) idade--; // corrige a contagem subtraindo 1 ano
  return idade;
}

// Feedback visual imediato de idade — isso é só UX.
// A validação que realmente protege o sistema tem que acontecer no back-end também,
// porque o front-end pode ser burlado facilmente.
// addEventListener registra uma função "callback" (aqui uma arrow function anônima)
// que o navegador chama automaticamente toda vez que o valor do campo de data muda.
campoData.addEventListener('change', () => {
  if (!campoData.value) return; // campo ainda vazio: nada a validar
  const idade = calcularIdade(campoData.value); // chama a função declarada acima
  if (idade < IDADE_MINIMA) {
    blocoIdade.style.display = 'block'; // mostra o aviso (ver .flori-age-block em style.css)
  } else {
    blocoIdade.style.display = 'none';  // esconde o aviso
  }
});

// Barra de força de senha — indicador visual simples, sem lista de regras punitivas
// Este listener roda a cada tecla digitada no campo de senha (evento 'input').
campoSenha.addEventListener('input', () => {
  const valor = campoSenha.value; // texto atual digitado no campo
  let forca = 0; // acumulador de 0 a 100, representando o "score" de força
  if (valor.length >= 8) forca += 33;                                   // +33 se tiver 6+ caracteres
  if (/[A-Z]/.test(valor) && /[a-z]/.test(valor)) forca += 33;          // +33 se misturar maiúscula e minúscula
  if (/[0-9]/.test(valor) || /[^A-Za-z0-9]/.test(valor)) forca += 34;   // +34 se tiver número ou símbolo

  // Atualiza a largura (preenchimento) e a cor da barra visual (.flori-strength-bar em style.css)
  // diretamente via style inline, proporcional ao score calculado acima.
  barraForca.style.width = forca + '%';
  barraForca.style.backgroundColor =
    forca < 40 ? '#b3261e' : forca < 75 ? '#e0a13f' : '#7ba75d'; // vermelho / laranja / verde
});

// Listener principal: dispara quando o formulário é enviado (clique no botão
// "Criar minha conta" ou Enter num campo). 'async' permite usar 'await' dentro,
// necessário para esperar a resposta do fetch() mais abaixo.
form.addEventListener('submit', async (e) => {
  e.preventDefault(); // impede o recarregamento padrão da página (comportamento nativo do <form>)

  // Esconde todas as mensagens de erro (elementos com classe .flori-error)
  // antes de revalidar, para não acumular avisos de tentativas anteriores.
  document.querySelectorAll('.flori-error').forEach(el => el.style.display = 'none');

  // Flag local: começa true e vira false assim que QUALQUER validação abaixo falhar.
  let valido = true;

  // --- Validação 1: idade mínima -----------------------------------
  const idade = calcularIdade(campoData.value);
  if (!campoData.value || idade < IDADE_MINIMA) {
    erroIdade.textContent = 'Ainda não é possível criar a conta com essa data de nascimento.';
    erroIdade.style.display = 'block';
    valido = false;
  }

  // --- Validação 2: pelo menos um contato (e-mail ou celular) ------
  const email = document.getElementById('email').value.trim();
  const celular = document.getElementById('celular').value.trim();
  if (!email && !celular) {
    document.getElementById('erroContato').style.display = 'block';
    valido = false;
  }

  // --- Validação 3: tamanho mínimo da senha -------------------------
  const senha = campoSenha.value;
  if (senha.length < 6) {
    document.getElementById('erroSenha').style.display = 'block';
    valido = false;
  }

  // --- Validação 4: confirmação de senha igual à senha --------------
  const confirmarSenha = document.getElementById('confirmarSenha').value;
  if (senha !== confirmarSenha) {
    document.getElementById('erroConfirmarSenha').style.display = 'block';
    valido = false;
  }

  // --- Validação 5: checkbox de termos de uso marcado ----------------
  if (!document.getElementById('termos').checked) {
    document.getElementById('erroTermos').style.display = 'block';
    valido = false;
  }

  // Se qualquer validação acima falhou, interrompe aqui (os erros já
  // foram exibidos na tela) e não chega a chamar o back-end.
  if (!valido) return;

  // Monta o objeto que vai virar o corpo (body) da requisição HTTP,
  // com as chaves no mesmo formato esperado pelo back-end
  // (ver backend/users/services.py -> CadastroUsuario.__init__).
  const payload = {
    nome: document.getElementById('nome').value.trim(),
    sobrenome: document.getElementById('sobrenome').value.trim(),
    apelido: document.getElementById('apelido').value.trim(),
    data_nascimento: campoData.value,   // já vem como 'AAAA-MM-DD' do <input type="date">
    email: email || null,
    celular: celular || null,
    senha: senha,
    termos_aceitos: true                // só chega até aqui se o checkbox estiver marcado (validação 5)
  };

  try {
    // fetch: faz a chamada HTTP ao back-end Django (users/urls.py -> 'api/usuarios').
    // 'await' pausa a execução desta função até a resposta chegar, sem travar a página.
    const resposta = await fetch('http://127.0.0.1:8000/api/usuarios', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload) // converte o objeto payload em texto JSON
    });

    // Decodifica o corpo da resposta (também JSON) de volta para objeto JS.
    const resultado = await resposta.json();

    if (resposta.status === 201) {
      // 201 Created: cadastro realizado com sucesso (ver views.py -> resposta_json(..., status=201)).
      document.getElementById('toastSucesso').style.display = 'block';
      form.reset(); // limpa todos os campos do formulário
    } else {
      // Qualquer outro status é erro: escolhe onde mostrar a mensagem
      // vinda do back-end (resultado.mensagem) dependendo do tipo de erro.
      // 409 (conflito de e-mail/celular já em uso) -> mostra no campo de contato;
      // qualquer outro (400, validação geral) -> mostra no campo de idade.
      const campoErro = resposta.status === 409
        ? document.getElementById('erroContato')
        : document.getElementById('erroIdade');
      campoErro.textContent = resultado.mensagem;
      campoErro.style.display = 'block';
    }
  } catch (erro) {
    // Cai aqui se o fetch falhar antes de obter qualquer resposta
    // (ex: back-end desligado, sem conexão, CORS bloqueado).
    alert('Não foi possível conectar ao servidor. Confere se o back-end está rodando.');
  }
});