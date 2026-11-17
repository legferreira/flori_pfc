import { iniciarAreaLogada } from '../compartilhado/area-logada.js';
import './comum.js';
import { desenharConteudo, podeSairDoConteudo } from './conteudo.js';
import { desenharDashboard } from './dashboard.js';
import { desenharUsuarios } from './usuarios.js';

const painel = document.getElementById('painel');
const ABAS = {
  'visao-geral': { desenhar: desenharDashboard },
  usuarios: { desenhar: desenharUsuarios },
  conteudo: { desenhar: desenharConteudo, sair: podeSairDoConteudo },
};
let abaAtual = 'visao-geral';

async function abrir(aba) {
  if (aba !== abaAtual && ABAS[abaAtual].sair && !(await ABAS[abaAtual].sair())) return;
  abaAtual = aba;
  document.querySelectorAll('[data-aba]').forEach((botao) => {
    botao.setAttribute('aria-selected', String(botao.dataset.aba === aba));
  });
  ABAS[aba].desenhar(painel);
}

document.querySelector('.flori-abas').addEventListener('click', (evento) => {
  const botao = evento.target.closest('[data-aba]');
  if (botao) abrir(botao.dataset.aba);
});
painel.addEventListener('click', (evento) => ABAS[abaAtual].clique?.(evento));
painel.addEventListener('change', (evento) => ABAS[abaAtual].mudanca?.(evento));

const perfil = await iniciarAreaLogada('admin');
if (perfil && perfil.perfil !== 'admin') {
  window.location.replace('home.html');
} else if (perfil) {
  abrir('visao-geral');
}
