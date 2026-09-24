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
  const hoje = new Date(); // instancia um objeto Date com a data/hora atual (fuso local, sem problema aqui)
  // new Date('AAAA-MM-DD') interpretaria a string como meia-noite UTC, e os
  // getters abaixo leem no fuso LOCAL — em fusos negativos (ex: Brasil, UTC-3)
  // isso "volta" um dia. Por isso o ano/mês/dia são extraídos direto da string,
  // sem nunca passar por um objeto Date.
  const [anoNasc, mesNasc, diaNasc] = dataNascStr.split('-').map(Number);
  let idade = hoje.getFullYear() - anoNasc; // diferença bruta de anos
  // Verifica se o aniversário deste ano ainda não chegou (mês menor,
  // ou mesmo mês com dia menor) — se sim, a pessoa ainda não completou o ano.
  // getMonth() é 0-indexado (0 = janeiro), por isso o +1 para comparar com mesNasc (1 = janeiro).
  const mesAtual = hoje.getMonth() + 1;
  const aindaNaoFezAniversario =
    mesAtual < mesNasc ||
    (mesAtual === mesNasc && hoje.getDate() < diaNasc);
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
    blocoIdade.style.display = 'block'; // mostra o aviso (ver .flori-age-block em css/formularios.css)
  } else {
    blocoIdade.style.display = 'none';  // esconde o aviso
  }
});

// Barra de força de senha — indicador visual simples, sem lista de regras punitivas
// Este listener roda a cada tecla digitada no campo de senha (evento 'input').
campoSenha.addEventListener('input', () => {
  const valor = campoSenha.value; // texto atual digitado no campo
  let forca = 0; // acumulador de 0 a 100, representando o "score" de força
  if (valor.length >= 6) forca += 33;                                   // +33 se tiver 6+ caracteres
  if (/[A-Z]/.test(valor) && /[a-z]/.test(valor)) forca += 33;          // +33 se misturar maiúscula e minúscula
  if (/[0-9]/.test(valor) || /[^A-Za-z0-9]/.test(valor)) forca += 34;   // +34 se tiver número ou símbolo

  // Atualiza a largura (preenchimento) e a cor da barra visual (.flori-strength-bar em css/cadastro.css)
  // diretamente via style inline, proporcional ao score calculado acima.
  barraForca.style.width = forca + '%';
  barraForca.style.backgroundColor =
    forca < 40 ? '#b3261e' : forca < 75 ? '#e0a13f' : '#7ba75d'; // vermelho / laranja / verde
});

// --- Passos do cadastro -------------------------------------------------
// Textos do topo do cartão para cada passo. A posição no array é o número
// do passo menos 1 (PASSOS[0] = passo 1), igual ao data-passo do HTML.
const PASSOS = [
  { titulo: 'Vamos te conhecer', subtitulo: 'É rapidinho, leva menos de 2 minutos.' },
  { titulo: 'Como você quer entrar?', subtitulo: 'É com ele que você vai fazer login no Flori.' },
  { titulo: 'Agora, uma senha', subtitulo: 'Pra deixar sua conta protegida.' },
];

// Passo 3 quando a conta é pelo Google: não tem senha, só os termos.
const PASSO_3_GOOGLE = { titulo: 'Quase lá!', subtitulo: 'Só falta aceitar os termos.' };

const botaoAvancar = document.getElementById('botaoAvancar');
const botaoVoltar = document.getElementById('botaoVoltar');
let passoAtual = 1;

// --- Cadastro pelo Google -------------------------------------------------
// Preenchido por cadastro-google.js depois do popup do Google quando ainda
// não existe conta: { idToken, email, nome, sobrenome }. Com ele, o passo 2
// mostra "Você vai entrar com o Google", o passo 3 não pede senha e o envio
// vai para POST /api/usuarios/google.
let modoGoogle = null;

function ativarModoGoogle(perfil) {
  modoGoogle = perfil;
  // Sugere nome/sobrenome do Google só se a pessoa ainda não digitou.
  const nome = document.getElementById('nome');
  const sobrenome = document.getElementById('sobrenome');
  if (!nome.value.trim()) nome.value = perfil.nome || '';
  if (!sobrenome.value.trim()) sobrenome.value = perfil.sobrenome || '';
  atualizarModoGoogle();
  // Escolheu o Google no passo 2: já pode ir para os termos.
  if (passoAtual === 2) irParaPasso(3);
}

function cancelarModoGoogle() {
  modoGoogle = null;
  sessionStorage.removeItem('flori_cadastro_google'); // senão volta ao recarregar
  atualizarModoGoogle();
}

// Mostra/esconde o que muda entre conta por e-mail/senha e conta pelo Google.
function atualizarModoGoogle() {
  document.getElementById('emailGoogle').textContent = modoGoogle ? modoGoogle.email : '';
  document.getElementById('googleConectado').hidden = !modoGoogle;
  document.getElementById('opcaoGoogle').hidden = !!modoGoogle;
  document.getElementById('camposContato').hidden = !!modoGoogle;
  document.getElementById('camposSenha').hidden = !!modoGoogle;
  if (passoAtual === 3) irParaPasso(3); // atualiza título do passo 3
}

document.getElementById('cancelarGoogle').addEventListener('click', cancelarModoGoogle);

// Mostra só o passo 'numero', atualiza topo do cartão, barra e botões.
function irParaPasso(numero) {
  passoAtual = numero;
  document.querySelectorAll('.flori-step').forEach(passo => {
    passo.hidden = Number(passo.dataset.passo) !== numero;
  });

  const textos = numero === 3 && modoGoogle ? PASSO_3_GOOGLE : PASSOS[numero - 1];
  document.getElementById('contadorPasso').textContent = `Passo ${numero} de ${PASSOS.length}`;
  document.getElementById('tituloPasso').textContent = textos.titulo;
  document.getElementById('subtituloPasso').textContent = textos.subtitulo;
  document.getElementById('barraProgresso').style.width = `${Math.round(numero / PASSOS.length * 100)}%`;

  botaoVoltar.hidden = numero === 1;
  botaoAvancar.textContent = numero === PASSOS.length ? 'Criar minha conta' : 'Continuar';

  // Leva o foco para o primeiro campo visível do passo novo (teclado e leitor
  // de tela continuam de onde a pessoa está, sem precisar voltar ao topo).
  const primeiroCampo = [...document.querySelectorAll(`.flori-step[data-passo="${numero}"] input`)]
    .find(campo => campo.offsetParent !== null);
  if (primeiroCampo) primeiroCampo.focus();
}

botaoVoltar.addEventListener('click', () => {
  esconderErros();
  irParaPasso(passoAtual - 1);
});

// Esconde todas as mensagens de erro (elementos com classe .flori-error)
// antes de revalidar, para não acumular avisos de tentativas anteriores.
function esconderErros() {
  document.querySelectorAll('.flori-error').forEach(el => el.style.display = 'none');
}

function mostrarErro(id, texto) {
  const elemento = document.getElementById(id);
  if (texto) elemento.textContent = texto;
  elemento.style.display = 'block';
}

// --- Validação de cada passo --------------------------------------------
// Cada função confere só os campos do seu passo e devolve true/false.
// Mesmas regras de antes, apenas separadas por passo.

function validarPasso1() {
  let valido = true;
  if (!document.getElementById('nome').value.trim() || !document.getElementById('sobrenome').value.trim()) {
    mostrarErro('erroNome');
    valido = false;
  }
  // Idade mínima (só UX — o back-end valida de novo)
  if (!campoData.value || calcularIdade(campoData.value) < IDADE_MINIMA) {
    mostrarErro('erroIdade', 'Ainda não é possível criar a conta com essa data de nascimento.');
    valido = false;
  }
  return valido;
}

function validarPasso2() {
  if (modoGoogle) return true; // o contato é o e-mail do Google
  const campoEmail = document.getElementById('email');
  const email = campoEmail.value.trim();
  if (!email) {
    mostrarErro('erroContato', 'Preenche o e-mail pra gente continuar.');
    return false;
  }
  // checkValidity usa a validação nativa do type="email" (formato algo@algo)
  if (!campoEmail.checkValidity()) {
    mostrarErro('erroContato', 'Confere o e-mail, parece que falta alguma coisa.');
    return false;
  }
  return true;
}

function validarPasso3() {
  let valido = true;
  const senha = campoSenha.value;
  // Conta pelo Google não tem senha.
  if (!modoGoogle && senha.length < 8) {
    mostrarErro('erroSenha');
    valido = false;
  }
  if (!modoGoogle && senha !== document.getElementById('confirmarSenha').value) {
    mostrarErro('erroConfirmarSenha');
    valido = false;
  }
  if (!document.getElementById('termos').checked) {
    mostrarErro('erroTermos');
    valido = false;
  }
  return valido;
}

const VALIDACOES = [validarPasso1, validarPasso2, validarPasso3];

// Listener principal: dispara no clique de "Continuar"/"Criar minha conta"
// ou no Enter em qualquer campo. Nos passos 1 e 2 só valida e avança;
// no último, envia tudo ao back-end. 'async' permite usar 'await' no fetch().
form.addEventListener('submit', async (e) => {
  e.preventDefault(); // impede o recarregamento padrão da página (comportamento nativo do <form>)
  esconderErros();

  if (!VALIDACOES[passoAtual - 1]()) return;

  if (passoAtual < PASSOS.length) {
    irParaPasso(passoAtual + 1);
    return;
  }

  if (modoGoogle) {
    await cadastrarComGoogle();
    return;
  }

  // Monta o objeto que vai virar o corpo (body) da requisição HTTP,
  // com as chaves no mesmo formato esperado pelo back-end
  // (ver backend/users/services.py -> CadastroUsuario.__init__).
  const payload = {
    nome: document.getElementById('nome').value.trim(),
    sobrenome: document.getElementById('sobrenome').value.trim(),
    apelido: document.getElementById('apelido').value.trim(),
    data_nascimento: campoData.value,   // já vem como 'AAAA-MM-DD' do <input type="date">
    email: document.getElementById('email').value.trim() || null,
    celular: document.getElementById('celular').value.trim() || null,
    senha: campoSenha.value,
    termos_aceitos: true                // só chega até aqui se o checkbox estiver marcado (validarPasso3)
  };

  // Trava o botão durante o envio, pra um duplo clique não criar dois pedidos.
  botaoAvancar.disabled = true;
  botaoAvancar.textContent = 'Criando sua conta...';

  try {
    // fetch: faz a chamada HTTP ao back-end Django (users/urls.py -> 'api/usuarios').
    const resposta = await fetch('http://127.0.0.1:8000/api/usuarios', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload) // converte o objeto payload em texto JSON
    });
    const resultado = await resposta.json();

    if (resposta.status === 201) {
      // 201 Created: troca o formulário pela tela de sucesso.
      form.hidden = true;
      document.querySelector('.flori-progress').hidden = true;
      document.getElementById('contadorPasso').hidden = true;
      document.getElementById('tituloPasso').textContent = `Prontinho, ${resultado.apelido}!`;
      document.getElementById('subtituloPasso').textContent = 'Sua conta no Flori foi criada.';
      document.getElementById('mensagemConcluido').textContent =
        payload.email ? 'Mandamos um e-mail de boas-vindas pra você. Agora é só entrar.' : 'Agora é só entrar.';
      document.getElementById('cadastroConcluido').hidden = false;
      return;
    }

    // Erro do back-end: volta para o passo do campo que causou o problema.
    // 409 = e-mail/celular já em uso -> passo 2. Qualquer outro (400) fica
    // no passo atual, na área de erro geral.
    if (resposta.status === 409) {
      irParaPasso(2);
      mostrarErro('erroContato', resultado.mensagem);
    } else {
      mostrarErro('erroGeral', resultado.mensagem);
    }
  } catch (erro) {
    // Cai aqui se o fetch falhar antes de obter qualquer resposta
    // (ex: back-end desligado, sem conexão, CORS bloqueado).
    mostrarErro('erroGeral', 'Não foi possível conectar ao servidor. Confere se o back-end está rodando.');
  }

  botaoAvancar.disabled = false;
  botaoAvancar.textContent = passoAtual === PASSOS.length ? 'Criar minha conta' : 'Continuar';
});

// Envio do cadastro pelo Google: o e-mail sai do token do Google (o back-end
// verifica o token de novo), então aqui vão só os dados que o Google não tem.
async function cadastrarComGoogle() {
  botaoAvancar.disabled = true;
  botaoAvancar.textContent = 'Criando sua conta...';

  try {
    const resposta = await fetch('http://127.0.0.1:8000/api/usuarios/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id_token: modoGoogle.idToken,
        nome: document.getElementById('nome').value.trim(),
        sobrenome: document.getElementById('sobrenome').value.trim(),
        apelido: document.getElementById('apelido').value.trim(),
        data_nascimento: campoData.value,
        termos_aceitos: true,
      })
    });
    const resultado = await resposta.json();

    if (resposta.status === 201) {
      // Conta criada e já logada (o back-end devolve o token de sessão).
      sessionStorage.removeItem('flori_cadastro_google');
      concluirLogin(resultado); // sessao.js
      return;
    }

    // 401: o login do Google vale 1 hora — expirou, precisa clicar de novo.
    // 409: esse e-mail do Google já tem conta. Nos dois, volta ao passo 2.
    if (resposta.status === 401 || resposta.status === 409) {
      sessionStorage.removeItem('flori_cadastro_google');
      cancelarModoGoogle();
      irParaPasso(2);
      mostrarErro('erroGoogle', resultado.mensagem);
    } else {
      mostrarErro('erroGeral', resultado.mensagem);
    }
  } catch (erro) {
    mostrarErro('erroGeral', 'Não foi possível conectar ao servidor. Confere se o back-end está rodando.');
  }

  botaoAvancar.disabled = false;
  botaoAvancar.textContent = 'Criar minha conta';
}