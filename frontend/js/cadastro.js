const form = document.getElementById('formCadastro');
const campoData = document.getElementById('dataNascimento');
const blocoIdade = document.getElementById('blocoIdade');
const erroIdade = document.getElementById('erroIdade');
const campoSenha = document.getElementById('senha');
const barraForca = document.getElementById('barraForca');

const IDADE_MINIMA = 13;

function calcularIdade(dataNascStr) {
  const hoje = new Date();
  const [anoNasc, mesNasc, diaNasc] = dataNascStr.split('-').map(Number);
  let idade = hoje.getFullYear() - anoNasc;
  const mesAtual = hoje.getMonth() + 1;
  const aindaNaoFezAniversario =
    mesAtual < mesNasc ||
    (mesAtual === mesNasc && hoje.getDate() < diaNasc);
  if (aindaNaoFezAniversario) idade--;
  return idade;
}

campoData.addEventListener('change', () => {
  if (!campoData.value) return;
  const idade = calcularIdade(campoData.value);
  if (idade < IDADE_MINIMA) {
    blocoIdade.style.display = 'block';
  } else {
    blocoIdade.style.display = 'none';
  }
});

campoSenha.addEventListener('input', () => {
  const valor = campoSenha.value;
  let forca = 0;
  if (valor.length >= 6) forca += 33;
  if (/[A-Z]/.test(valor) && /[a-z]/.test(valor)) forca += 33;
  if (/[0-9]/.test(valor) || /[^A-Za-z0-9]/.test(valor)) forca += 34;

  barraForca.style.width = forca + '%';
  barraForca.style.backgroundColor =
    forca < 40 ? '#b3261e' : forca < 75 ? '#e0a13f' : '#7ba75d';
});

const PASSOS = [
  { titulo: 'Vamos te conhecer', subtitulo: 'É rapidinho, leva menos de 2 minutos.' },
  { titulo: 'Como você quer entrar?', subtitulo: 'É com ele que você vai fazer login no Flori.' },
  { titulo: 'Agora, uma senha', subtitulo: 'Pra deixar sua conta protegida.' },
];

const PASSO_3_GOOGLE = { titulo: 'Quase lá!', subtitulo: 'Só falta aceitar os termos.' };

const botaoAvancar = document.getElementById('botaoAvancar');
const botaoVoltar = document.getElementById('botaoVoltar');
let passoAtual = 1;

let modoGoogle = null;

function ativarModoGoogle(perfil) {
  modoGoogle = perfil;
  const nome = document.getElementById('nome');
  const sobrenome = document.getElementById('sobrenome');
  if (!nome.value.trim()) nome.value = perfil.nome || '';
  if (!sobrenome.value.trim()) sobrenome.value = perfil.sobrenome || '';
  atualizarModoGoogle();
  if (passoAtual === 2) irParaPasso(3);
}

function cancelarModoGoogle() {
  modoGoogle = null;
  sessionStorage.removeItem('flori_cadastro_google');
  atualizarModoGoogle();
}

function atualizarModoGoogle() {
  document.getElementById('emailGoogle').textContent = modoGoogle ? modoGoogle.email : '';
  document.getElementById('googleConectado').hidden = !modoGoogle;
  document.getElementById('opcaoGoogle').hidden = !!modoGoogle;
  document.getElementById('camposContato').hidden = !!modoGoogle;
  document.getElementById('camposSenha').hidden = !!modoGoogle;
  if (passoAtual === 3) irParaPasso(3);
}

document.getElementById('cancelarGoogle').addEventListener('click', cancelarModoGoogle);

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

  const primeiroCampo = [...document.querySelectorAll(`.flori-step[data-passo="${numero}"] input`)]
    .find(campo => campo.offsetParent !== null);
  if (primeiroCampo) primeiroCampo.focus();
}

botaoVoltar.addEventListener('click', () => {
  esconderErros();
  irParaPasso(passoAtual - 1);
});

function esconderErros() {
  document.querySelectorAll('.flori-error').forEach(el => el.style.display = 'none');
}

function mostrarErro(id, texto) {
  const elemento = document.getElementById(id);
  if (texto) elemento.textContent = texto;
  elemento.style.display = 'block';
}

function validarPasso1() {
  let valido = true;
  if (!document.getElementById('nome').value.trim() || !document.getElementById('sobrenome').value.trim()) {
    mostrarErro('erroNome');
    valido = false;
  }
  if (!campoData.value || calcularIdade(campoData.value) < IDADE_MINIMA) {
    mostrarErro('erroIdade', 'Ainda não é possível criar a conta com essa data de nascimento.');
    valido = false;
  }
  return valido;
}

function validarPasso2() {
  if (modoGoogle) return true;
  const campoEmail = document.getElementById('email');
  const email = campoEmail.value.trim();
  if (!email) {
    mostrarErro('erroContato', 'Preenche o e-mail pra gente continuar.');
    return false;
  }
  if (!campoEmail.checkValidity()) {
    mostrarErro('erroContato', 'Confere o e-mail, parece que falta alguma coisa.');
    return false;
  }
  return true;
}

function validarPasso3() {
  let valido = true;
  const senha = campoSenha.value;
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

form.addEventListener('submit', async (e) => {
  e.preventDefault();
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

  const payload = {
    nome: document.getElementById('nome').value.trim(),
    sobrenome: document.getElementById('sobrenome').value.trim(),
    apelido: document.getElementById('apelido').value.trim(),
    data_nascimento: campoData.value,
    email: document.getElementById('email').value.trim() || null,
    celular: document.getElementById('celular').value.trim() || null,
    senha: campoSenha.value,
    termos_aceitos: true
  };

  botaoAvancar.disabled = true;
  botaoAvancar.textContent = 'Criando sua conta...';

  try {
    const resposta = await fetch('http://127.0.0.1:8000/api/usuarios', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const resultado = await resposta.json();

    if (resposta.status === 201) {
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

    if (resposta.status === 409) {
      irParaPasso(2);
      mostrarErro('erroContato', resultado.mensagem);
    } else {
      mostrarErro('erroGeral', resultado.mensagem);
    }
  } catch (erro) {
    mostrarErro('erroGeral', 'Não foi possível conectar ao servidor. Confere se o back-end está rodando.');
  }

  botaoAvancar.disabled = false;
  botaoAvancar.textContent = passoAtual === PASSOS.length ? 'Criar minha conta' : 'Continuar';
});

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
      sessionStorage.removeItem('flori_cadastro_google');
      concluirLogin(resultado);
      return;
    }

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
