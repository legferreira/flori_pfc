import { chamarApi, iniciarAreaLogada } from './compartilhado/area-logada.js';
import { popupCard, popupGuia } from './trilha/popup.js';
import {
  telaAssunto, telaCertificado, telaQuiz, telaResultado, telaTrilha,
} from './trilha/telas.js';

const conteudo = document.getElementById('conteudo');
const dialogo = document.getElementById('dialogCard');
const dialogoConteudo = document.getElementById('dlgConteudo');

let dados = null;
let destino = 'trilha';
let quiz = null;
let quizEstado = null;
let cardAberto = null;

const assuntoPorId = (id) => dados.assuntos.find((a) => a.id === id);

async function carregarTrilha() {
  const { ok, dados: corpo } = await chamarApi('/trilha');
  if (!ok) throw new Error(corpo.mensagem || 'Não foi possível carregar a trilha.');
  dados = corpo;
}

function mostrarErro(mensagem) {
  conteudo.innerHTML = `<div class="flori-card text-center">
    <p class="mb-3">${mensagem}</p>
    <button type="button" class="btn btn-flori btn-flori-sm" data-recarregar>Tentar de novo</button></div>`;
}

function destinoDoEndereco() {
  return window.location.hash.replace('#', '') || 'trilha';
}

async function ir(novo) {
  destino = novo;
  if (novo === 'quiz') quizEstado = null;
  try { history.pushState(null, '', `#${novo}`); } catch {}
  await mostrarTela();
}

async function mostrarTela() {
  const [vista, id] = destino.split('/');
  try {
    if (vista === 'quiz') await prepararQuiz();
    else quizEstado = null;
    if (vista === 'certificado' && !dados.certificado) destino = 'trilha';

    if (vista === 'quiz' && quizEstado) conteudo.innerHTML = quizEstado.resultado ? telaResultado(quizEstado.resultado) : telaQuiz(quiz, quizEstado);
    else if (vista === 'certificado' && dados.certificado) conteudo.innerHTML = telaCertificado(dados.certificado);
    else if (vista === 'trilha' && id) conteudo.innerHTML = telaAssunto(dados, id);
    else conteudo.innerHTML = telaTrilha(dados);
  } catch (erro) {
    mostrarErro(erro.message);
    return;
  }
  window.scrollTo(0, 0);
  document.getElementById('perguntaTitulo')?.focus({ preventScroll: true });
}

async function prepararQuiz() {
  if (quizEstado) return;
  const { ok, status, dados: corpo } = await chamarApi('/trilha/quiz');
  if (!ok) {
    if (status === 403) { destino = 'trilha'; quizEstado = null; return; }
    throw new Error(corpo.mensagem || 'Não foi possível carregar o quiz.');
  }
  quiz = corpo;
  quizEstado = { indice: 0, respostas: {}, resultado: null, enviando: false, erro: '' };
}

async function enviarQuiz() {
  quizEstado.enviando = true;
  quizEstado.erro = '';
  conteudo.innerHTML = telaQuiz(quiz, quizEstado);
  try {
    const { ok, dados: corpo } = await chamarApi('/trilha/quiz', { metodo: 'POST', corpo: { respostas: quizEstado.respostas } });
    if (!ok) throw new Error(corpo.mensagem || 'Não foi possível enviar o quiz.');
    quizEstado.resultado = corpo;
    await carregarTrilha();
  } catch (erro) {
    quizEstado.erro = erro.message || 'Sem conexão. Tente de novo.';
  }
  quizEstado.enviando = false;
  conteudo.innerHTML = quizEstado.resultado ? telaResultado(quizEstado.resultado) : telaQuiz(quiz, quizEstado);
}

function cliqueNoQuiz(acao) {
  if (acao === 'ant' && quizEstado.indice > 0) quizEstado.indice -= 1;
  else if (acao === 'prox' && quizEstado.indice < quiz.perguntas.length - 1) quizEstado.indice += 1;
  else if (acao === 'prox') { enviarQuiz(); return; }
  conteudo.innerHTML = telaQuiz(quiz, quizEstado);
  document.getElementById('perguntaTitulo').focus({ preventScroll: true });
}

function mostrarPopup() {
  if (!dialogo.open) {
    try { dialogo.showModal(); } catch { dialogo.setAttribute('open', ''); }
  }
}

function desenharCard() {
  const assunto = assuntoPorId(cardAberto.assuntoId);
  dialogoConteudo.innerHTML = popupCard({ dados, assunto, ...cardAberto });
}

function abrirCard(assuntoId, indice) {
  cardAberto = { assuntoId, indice: Number(indice), aviso: '', salvando: false };
  desenharCard();
  mostrarPopup();
}

function abrirGuia() {
  cardAberto = null;
  dialogoConteudo.innerHTML = popupGuia(dados.guia_rapido);
  mostrarPopup();
}

async function concluirCard() {
  const assunto = assuntoPorId(cardAberto.assuntoId);
  const card = assunto.cards[cardAberto.indice];
  cardAberto.salvando = true;
  desenharCard();

  try {
    const { ok, dados: corpo } = await chamarApi(`/trilha/cards/${card.id}/concluir`, { metodo: 'POST' });
    if (!ok) throw new Error(corpo.mensagem);
    await carregarTrilha();
    const atualizado = assuntoPorId(cardAberto.assuntoId);
    cardAberto.aviso = dados.concluidos === dados.total_cards
      ? 'Trilha concluída! O quiz final foi liberado.'
      : atualizado.concluidos === atualizado.total ? 'Assunto concluído, parabéns!' : 'Progresso salvo.';
  } catch {
    cardAberto.aviso = 'Não foi possível salvar agora. Tente de novo.';
  }
  cardAberto.salvando = false;
  desenharCard();
}

document.addEventListener('click', (e) => {
  const alvo = (seletor) => e.target.closest(seletor);

  const link = alvo('a[href^="#"]');
  if (link) { e.preventDefault(); ir(link.getAttribute('href').slice(1)); return; }
  if (alvo('[data-ir]')) { ir(alvo('[data-ir]').dataset.ir); return; }
  if (alvo('[data-recarregar]')) { init(); return; }
  if (alvo('[data-socorro]')) { abrirGuia(); return; }
  if (alvo('[data-abrir]')) { abrirCard(...alvo('[data-abrir]').dataset.abrir.split(':')); return; }
  if (alvo('[data-concluir]')) { concluirCard(); return; }
  if (alvo('[data-quiz-pronto]')) { dialogo.close(); ir('trilha'); return; }
  if (alvo('[data-fechar]')) { dialogo.close(); return; }
  if (alvo('[data-nav]')) {
    cardAberto.indice += Number(alvo('[data-nav]').dataset.nav);
    cardAberto.aviso = '';
    desenharCard();
    dialogo.scrollTop = 0;
    return;
  }
  if (alvo('[data-quiz]') && quizEstado) { cliqueNoQuiz(alvo('[data-quiz]').dataset.quiz); return; }
  if (alvo('[data-imprimir]')) { window.print(); return; }
  if (e.target === dialogo) dialogo.close();
});

document.addEventListener('change', (e) => {
  if (e.target.name !== 'opcao' || !quizEstado) return;
  quizEstado.respostas[quiz.perguntas[quizEstado.indice].id] = e.target.value;
  document.querySelectorAll('.flori-opcao').forEach((l) => l.classList.toggle('is-marcada', l.contains(e.target)));
  document.getElementById('btnProx').disabled = false;
});

dialogo.addEventListener('close', () => {
  if (cardAberto) mostrarTela();
  cardAberto = null;
});

window.addEventListener('popstate', () => { destino = destinoDoEndereco(); mostrarTela(); });

async function init() {
  if (!(await iniciarAreaLogada('trilha'))) return;
  try {
    await carregarTrilha();
  } catch (erro) {
    mostrarErro(erro.message || 'Sem conexão com o servidor.');
    return;
  }
  destino = destinoDoEndereco();
  await mostrarTela();
}

init();
