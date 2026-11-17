import { dataCurta, esc, ICONE_OK } from '../compartilhado/componentes.js';

const ICONE_FECHAR = '<svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true"><path d="M4 4l10 10M14 4L4 14" stroke="#3E2F59" stroke-width="2" stroke-linecap="round"/></svg>';

function topo(cor, texto) {
  return `<div class="flori-dialog-topo" style="--cor:${esc(cor)}">
    <span>${texto}</span>
    <button type="button" class="flori-dialog-fechar" data-fechar aria-label="Fechar">${ICONE_FECHAR}</button>
  </div>`;
}

function fontes(lista) {
  if (!lista || !lista.length) return '';
  const links = lista.map((f) => `<a href="${esc(f.url)}" target="_blank" rel="noopener noreferrer">${esc(f.nome)}</a>`);
  return `<p class="flori-fonte">Fonte${lista.length > 1 ? 's' : ''}: ${links.join('; ')}</p>`;
}

export function popupGuia(guia) {
  const passos = guia.passos.map((p) => `<li>${esc(p)}</li>`).join('');
  return `${topo('#EDBFD8', 'Fora da trilha, não conta no progresso')}
    <div class="flori-dialog-corpo">
      <h2 class="flori-heading" id="dlgTema">${esc(guia.titulo)}</h2>
      ${guia.introducao ? `<p class="flori-explicacao">${esc(guia.introducao)}</p>` : ''}
      <ol class="flori-passos">${passos}</ol>
      ${fontes(guia.fontes)}
      <button type="button" class="btn btn-flori" data-fechar>Entendi</button>
    </div>`;
}

export function popupCard({ dados, assunto, indice, aviso, salvando }) {
  const card = assunto.cards[indice];
  const ultimo = indice === assunto.cards.length - 1;
  const leitura = dados.modo_visualizacao;
  const trilhaCompleta = !leitura && dados.concluidos === dados.total_cards;

  const secoes = card.secoes.map((s) => `
    <h3 class="flori-heading flori-secao">${esc(s.titulo)}</h3>
    <ul class="flori-itens">${s.itens.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>`).join('');

  const botaoConcluir = leitura ? '' : card.concluido
    ? `<button type="button" class="btn btn-flori flori-btn-concluido" disabled>${ICONE_OK} Concluído em ${dataCurta(card.concluido_em)}</button>`
    : `<button type="button" class="btn btn-flori" data-concluir ${salvando ? 'disabled' : ''}>Marcar como concluído</button>`;

  let avancar;
  if (trilhaCompleta && ultimo && card.concluido) {
    avancar = '<button type="button" class="btn btn-flori btn-flori-sm" data-fechar data-quiz-pronto>Ir para o quiz</button>';
  } else if (!ultimo) {
    avancar = `<button type="button" class="btn btn-flori-outline btn-flori-sm" data-nav="1">${card.concluido || leitura ? 'Próximo card →' : 'Pular →'}</button>`;
  } else {
    avancar = `<button type="button" class="btn btn-flori-outline btn-flori-sm" data-fechar>${!leitura && assunto.concluidos === assunto.total ? 'Voltar ao assunto' : 'Fechar'}</button>`;
  }

  return `${topo(assunto.cor, `${esc(assunto.titulo)}, card ${indice + 1} de ${assunto.cards.length}`)}
    <div class="flori-dialog-corpo">
      <h2 class="flori-heading" id="dlgTema">${esc(card.tema)}</h2>
      <p class="flori-explicacao">${esc(card.explicacao)}</p>
      ${secoes}
      ${card.exemplo ? `<p class="flori-exemplo"><strong>Exemplo</strong>${esc(card.exemplo)}</p>` : ''}
      ${fontes(card.fontes)}
      ${card.aviso ? `<p class="flori-aviso-extra" role="note">${esc(card.aviso)}</p>` : ''}
      ${card.cta ? `<div class="flori-cta-extra">${esc(card.cta)}<br><a class="btn btn-flori-outline btn-flori-sm" href="diario.html">Abrir o diário do corpo</a></div>` : ''}
      ${botaoConcluir}
      ${leitura ? '' : `<p class="flori-sucesso" role="status" aria-live="polite">${aviso ? esc(aviso) : ''}</p>`}
      <div class="flori-dialog-nav">
        <button type="button" class="btn btn-flori-outline btn-flori-sm" data-nav="-1" ${indice === 0 ? 'disabled' : ''}>← Anterior</button>
        ${avancar}
      </div>
    </div>`;
}
