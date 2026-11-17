import { chamarApi } from '../compartilhado/area-logada.js';
import { popupCard, popupGuia } from '../trilha/popup.js';
import { blocoPergunta } from '../trilha/telas.js';
import {
  ICONES, botao, chip, confirmarDescarte, dataDiaMes, el, icone, mostrarErroCampo, toast,
} from './interface.js';

export const SEM_CONEXAO = 'Sem conexão com o servidor. Verifique a internet e tente de novo.';

export async function api(caminho, opcoes) {
  try {
    return await chamarApi(`/admin/conteudo${caminho}`, opcoes);
  } catch {
    return { ok: false, status: 0, dados: { mensagem: SEM_CONEXAO } };
  }
}

let editorAberto = null;

export const editores = {
  abrir(editor) { editorAberto = editor; },
  soltar(editor) { if (editorAberto === editor) editorAberto = null; },
  atual() { return editorAberto; },
  pendente() { return Boolean(editorAberto && editorAberto.sujo()); },
  async liberar() {
    if (!editorAberto) return true;
    if (editorAberto.sujo() && !(await confirmarDescarte())) return false;
    const editor = editorAberto;
    editorAberto = null;
    editor.fechar();
    return true;
  },
};

window.addEventListener('beforeunload', (evento) => {
  if (editores.pendente()) {
    evento.preventDefault();
    evento.returnValue = '';
  }
});

export function caixaResumo() {
  return el('div', { class: 'flori-ct-resumo-erro', role: 'alert', tabindex: '-1', hidden: true });
}

export function limparErros(resumo, campos) {
  resumo.hidden = true;
  resumo.replaceChildren();
  Object.values(campos).forEach((campo) => mostrarErroCampo(campo, ''));
}

export function mostrarFalha(resposta, { resumo, campos = {}, aoRecarregar }) {
  const { status, dados } = resposta;
  resumo.replaceChildren(el('p', { text: dados.mensagem || 'Não foi possível salvar.' }));
  const soltos = [];
  Object.entries(dados.campos || {}).forEach(([chave, mensagem]) => {
    const campo = campos[chave];
    if (campo) mostrarErroCampo(campo, mensagem);
    else soltos.push(mensagem);
  });
  if (soltos.length) resumo.append(el('ul', {}, soltos.map((m) => el('li', { text: m }))));
  if (status === 409 && aoRecarregar) {
    resumo.append(botao('Recarregar', { onclick: aoRecarregar }, 'secundario'));
  }
  resumo.hidden = false;
  resumo.focus();
}

export function botaoSalvar(texto, aoSalvar, podeSalvar = () => true) {
  const elemento = botao(texto, {}, 'primario');
  elemento.addEventListener('click', async () => {
    if (elemento.disabled) return;
    elemento.disabled = true;
    elemento.textContent = 'Salvando...';
    try {
      await aoSalvar();
    } finally {
      elemento.textContent = texto;
      elemento.disabled = !podeSalvar();
    }
  });
  elemento.disabled = !podeSalvar();
  return elemento;
}

const dialogo = () => document.getElementById('dialogPrevia');
const conteudoDialogo = () => document.getElementById('previaConteudo');

function abrirPrevia(html) {
  conteudoDialogo().innerHTML = html;
  const caixa = dialogo();
  if (!caixa.open) caixa.showModal();
  caixa.querySelector('[data-fechar]')?.focus();
}

export function previaCard(card, assunto) {
  const assuntoPrevia = { ...assunto, cards: [card], concluidos: 0, total: 1 };
  abrirPrevia(popupCard({
    dados: { modo_visualizacao: true, concluidos: 0, total_cards: 1 },
    assunto: assuntoPrevia, indice: 0, aviso: '', salvando: false,
  }));
}

export function previaGuia(guia) {
  abrirPrevia(popupGuia(guia));
}

export function previaPergunta(pergunta) {
  abrirPrevia(`<div class="flori-dialog-topo" style="--cor:#EDBFD8"><span>Quiz final, modo visualização</span>
      <button type="button" class="flori-dialog-fechar" data-fechar aria-label="Fechar">&times;</button></div>
    <div class="flori-dialog-corpo">${blocoPergunta(pergunta, undefined, true)}
      <button type="button" class="btn btn-flori" data-fechar>Fechar</button></div>`);
}

document.addEventListener('click', (evento) => {
  const caixa = dialogo();
  if (!caixa || !caixa.open) return;
  if (evento.target === caixa || evento.target.closest('#dialogPrevia [data-fechar]')) caixa.close();
});

export function plural(n, singular, pluralTexto) {
  return `${n} ${n === 1 ? singular : pluralTexto}`;
}

export function chipSituacao(item, feminino = false) {
  const fim = feminino ? 'a' : 'o';
  if (item.excluido_em) return chip(`excluíd${fim} em ${dataDiaMes(item.excluido_em)}`, 'is-excluido');
  return item.ativo ? chip(`ativ${fim}`, 'is-ativo') : chip(`desativad${fim}`, 'is-desativado');
}

export function caixaExcluidos(rotulo, marcado, aoMudar) {
  const entrada = el('input', { type: 'checkbox', class: 'form-check-input', checked: marcado });
  entrada.addEventListener('change', async () => {
    const pedido = entrada.checked;
    if (!(await editores.liberar())) {
      entrada.checked = !pedido;
      return;
    }
    aoMudar(pedido);
  });
  return el('label', { class: 'flori-ct-check' }, entrada, el('span', { text: rotulo }));
}

export function setas({ nome, numero, posicao, total, chave, aoMover }) {
  return el('span', { class: 'flori-ct-setas' },
    el('button', {
      type: 'button', class: 'flori-ct-seta', 'aria-label': `Subir ${nome} ${numero}`, 'data-foco': `${chave}:subir`,
      disabled: posicao <= 0, onclick: () => aoMover('subir'),
    }, icone(ICONES.subir)),
    el('button', {
      type: 'button', class: 'flori-ct-seta', 'aria-label': `Descer ${nome} ${numero}`, 'data-foco': `${chave}:descer`,
      disabled: posicao >= total - 1, onclick: () => aoMover('descer'),
    }, icone(ICONES.descer)));
}

export function caixaMensagem() {
  return el('div', { class: 'flori-ct-mensagem', role: 'alert', hidden: true });
}

export function mostrarMensagem(caixa, texto) {
  caixa.textContent = texto || '';
  caixa.hidden = !texto;
}

export async function executarAcao({ caminho, corpo, caixa, sucesso, depois }) {
  if (!(await editores.liberar())) return null;
  mostrarMensagem(caixa, '');
  const resposta = await api(caminho, { metodo: 'POST', corpo: corpo ?? {} });
  if (!resposta.ok) {
    mostrarMensagem(caixa, resposta.dados.mensagem || 'Não foi possível concluir a ação.');
    return resposta;
  }
  if (sucesso) toast(sucesso);
  await depois?.(resposta);
  return resposta;
}
