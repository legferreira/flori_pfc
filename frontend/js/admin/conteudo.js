import { editores } from './conteudo-comum.js';
import { desenharGuias } from './conteudo-guias.js';
import { desenharQuiz } from './conteudo-quiz.js';
import { desenharTrilha } from './conteudo-trilha.js';
import { el } from './interface.js';

const SUBABAS = [
  { id: 'trilha', rotulo: 'Trilha de conteúdo', desenhar: desenharTrilha },
  { id: 'quiz', rotulo: 'Perguntas do quiz', desenhar: desenharQuiz },
  { id: 'guias', rotulo: 'Guias rápidos', desenhar: desenharGuias },
];

let subAtual = 'trilha';

export function desenharConteudo(painel) {
  const area = el('div', { class: 'flori-ct-area', id: 'areaConteudo', role: 'tabpanel' });
  const botoes = SUBABAS.map((sub) => el('button', {
    type: 'button', role: 'tab', class: 'flori-ct-subaba', id: `subaba_${sub.id}`,
    'aria-selected': String(sub.id === subAtual), 'aria-controls': 'areaConteudo',
    tabindex: sub.id === subAtual ? '0' : '-1', text: sub.rotulo,
    onclick: () => trocar(sub.id),
  }));
  const lista = el('div', { class: 'flori-ct-subabas', role: 'tablist', 'aria-label': 'Tipos de conteúdo' }, botoes);
  lista.addEventListener('keydown', (evento) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(evento.key)) return;
    const indice = SUBABAS.findIndex((s) => s.id === subAtual);
    const passo = evento.key === 'ArrowRight' ? 1 : -1;
    const proxima = SUBABAS[(indice + passo + SUBABAS.length) % SUBABAS.length];
    trocar(proxima.id, true);
  });
  painel.replaceChildren(el('section', { class: 'flori-painel flori-ct' }, lista, area));
  abrirSubaba(subAtual);

  async function trocar(id, focar = false) {
    if (id === subAtual) return;
    if (!(await editores.liberar())) return;
    subAtual = id;
    botoes.forEach((botao, i) => {
      const ativa = SUBABAS[i].id === id;
      botao.setAttribute('aria-selected', String(ativa));
      botao.tabIndex = ativa ? 0 : -1;
      if (ativa && focar) botao.focus();
    });
    abrirSubaba(id);
  }

  function abrirSubaba(id) {
    const sub = SUBABAS.find((s) => s.id === id);
    area.setAttribute('aria-labelledby', `subaba_${id}`);
    sub.desenhar(area);
  }
}

export function podeSairDoConteudo() {
  return editores.liberar();
}
