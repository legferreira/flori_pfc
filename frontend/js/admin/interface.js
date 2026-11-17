import { el } from '../compartilhado/dom.js';

export { el };

export function icone(svg) {
  const span = el('span', { class: 'flori-ct-icone', 'aria-hidden': 'true' });
  span.innerHTML = svg;
  return span;
}

export const ICONES = {
  seta: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  subir: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M3.5 10L8 5.5l4.5 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  descer: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M3.5 6L8 10.5 12.5 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  certo: '<svg width="18" height="18" viewBox="0 0 16 16" fill="none"><path d="M3 8.5l3.2 3L13 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  alerta: '<svg width="18" height="18" viewBox="0 0 16 16" fill="none"><path d="M8 2l6.5 11.5h-13L8 2z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M8 6.5v3.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><circle cx="8" cy="11.8" r="0.9" fill="currentColor"/></svg>',
};

export function dataDiaMes(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit' });
}

let temporizadorToast = null;

export function toast(texto) {
  const caixa = document.getElementById('toastAdmin');
  caixa.textContent = texto;
  caixa.hidden = false;
  caixa.classList.add('is-visivel');
  clearTimeout(temporizadorToast);
  temporizadorToast = setTimeout(() => {
    caixa.classList.remove('is-visivel');
    caixa.hidden = true;
  }, 2000);
}

export function confirmar({ titulo, texto, itens = [], rotuloConfirmar = 'Excluir', rotuloCancelar = 'Cancelar', perigo = true }) {
  const modal = document.getElementById('modalConfirmar');
  const lista = document.getElementById('itensConfirmar');
  const botaoConfirmar = document.getElementById('botaoConfirmar');
  const botaoCancelar = document.getElementById('botaoCancelarConfirmar');
  document.getElementById('tituloConfirmar').textContent = titulo;
  document.getElementById('textoConfirmar').textContent = texto;
  lista.replaceChildren(...itens.map((item) => el('li', { text: item })));
  lista.hidden = !itens.length;
  botaoConfirmar.textContent = rotuloConfirmar;
  botaoConfirmar.className = perigo ? 'btn btn-perigo' : 'btn btn-flori';
  botaoCancelar.textContent = rotuloCancelar;

  return new Promise((resolver) => {
    const anterior = document.activeElement;
    const terminar = (resposta) => {
      botaoConfirmar.removeEventListener('click', aoConfirmar);
      botaoCancelar.removeEventListener('click', aoCancelar);
      modal.removeEventListener('close', aoFechar);
      if (modal.open) modal.close();
      if (anterior && document.contains(anterior)) anterior.focus();
      resolver(resposta);
    };
    const aoConfirmar = () => terminar(true);
    const aoCancelar = () => terminar(false);
    const aoFechar = () => terminar(false);
    botaoConfirmar.addEventListener('click', aoConfirmar);
    botaoCancelar.addEventListener('click', aoCancelar);
    modal.addEventListener('close', aoFechar);
    modal.showModal();
    botaoCancelar.focus();
  });
}

export function confirmarDescarte() {
  return confirmar({
    titulo: 'Você tem alterações não salvas',
    texto: 'Se continuar, as alterações deste editor serão perdidas.',
    rotuloConfirmar: 'Descartar alterações',
    rotuloCancelar: 'Continuar editando',
  });
}

export function campoTexto({ id, rotulo, valor = '', maximo, area = false, linhas = 3, aoMudar, classe = '' }) {
  const contador = el('small', { class: 'flori-ct-contador', id: `${id}_contador`, 'aria-live': 'off' });
  const erro = el('small', { class: 'flori-ct-erro-campo', id: `${id}_erro`, hidden: true });
  const atualizar = () => { contador.textContent = `${entrada.value.length} de ${maximo}`; };
  const entrada = el(area ? 'textarea' : 'input', {
    class: `form-control ${classe}`.trim(), id, maxlength: maximo, rows: area ? linhas : undefined,
    type: area ? undefined : 'text', 'aria-describedby': `${id}_contador`,
    oninput: () => { atualizar(); aoMudar?.(); },
  });
  entrada.value = valor;
  atualizar();
  const bloco = el('div', { class: 'flori-ct-campo' },
    rotulo ? el('label', { class: 'form-label', for: id, text: rotulo }) : null,
    entrada,
    el('div', { class: 'flori-ct-campo-pe' }, erro, contador));
  return { bloco, entrada, erro };
}

export function mostrarErroCampo(campo, mensagem) {
  const descricao = [`${campo.entrada.id}_contador`];
  if (mensagem) {
    campo.erro.textContent = mensagem;
    campo.erro.hidden = false;
    campo.entrada.setAttribute('aria-invalid', 'true');
    descricao.unshift(campo.erro.id);
  } else {
    campo.erro.textContent = '';
    campo.erro.hidden = true;
    campo.entrada.removeAttribute('aria-invalid');
  }
  campo.entrada.setAttribute('aria-describedby', descricao.join(' '));
}

export function chip(texto, tipo = '') {
  return el('span', { class: `flori-ct-chip ${tipo}`.trim(), text: texto });
}

export function botao(texto, props = {}, tipo = 'secundario') {
  const classes = {
    primario: 'btn btn-flori btn-flori-sm',
    secundario: 'btn btn-flori-outline btn-flori-sm',
    perigo: 'btn flori-ct-btn-perigo btn-flori-sm',
    link: 'flori-ct-link',
  };
  return el('button', { type: 'button', class: classes[tipo], text: texto, ...props });
}

export function estadoCarregando(texto = 'Carregando...') {
  return el('p', { class: 'flori-hint flori-ct-estado', role: 'status', text: texto });
}

export function estadoErro(texto, aoTentar, rotulo = 'Tentar novamente') {
  return el('div', { class: 'flori-ct-estado flori-ct-estado-erro', role: 'alert' },
    el('p', { text: texto }),
    botao(rotulo, { onclick: aoTentar }, 'primario'));
}

export function estadoVazio(texto, rotulo, aoCriar) {
  return el('div', { class: 'flori-ct-vazio' },
    el('p', { text: texto }),
    botao(rotulo, { onclick: aoCriar }, 'primario'));
}

export function focarDepois(chave) {
  if (!chave) return;
  requestAnimationFrame(() => {
    const alvo = document.querySelector(`[data-foco="${CSS.escape(chave)}"]`);
    if (alvo && !alvo.disabled) alvo.focus();
  });
}
