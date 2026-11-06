export const esc = (texto) => String(texto).replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

export const percentual = (parte, total) => (total ? Math.round((parte / total) * 100) : 0);

export function flor(cor, tamanho, classe = 'flori-assunto-flor') {
  return `<svg class="${classe}" width="${tamanho}" height="${tamanho}" viewBox="0 0 28 28" fill="none" aria-hidden="true">
    <circle cx="14" cy="8" r="5" fill="${cor}"/><circle cx="20" cy="14" r="5" fill="${cor}"/>
    <circle cx="14" cy="20" r="5" fill="${cor}"/><circle cx="8" cy="14" r="5" fill="${cor}"/>
    <circle cx="14" cy="14" r="3.5" fill="#3E2F59"/></svg>`;
}

export function barra(feitos, total) {
  return `<div class="flori-barra" role="progressbar" aria-valuemin="0" aria-valuemax="${total}" aria-valuenow="${feitos}"><span style="width:${percentual(feitos, total)}%"></span></div>`;
}

export const ICONE_OK = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M3 8.5l3.2 3L13 4.5" stroke="#3E2F59" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
export const ICONE_CADEADO = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2" stroke="#3E2F59" stroke-width="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3" stroke="#3E2F59" stroke-width="2" stroke-linecap="round"/></svg>';
export const ICONE_QUIZ = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="#3E2F59" stroke-width="2"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.6 2.2c-.7.4-1.1.9-1.1 1.8" stroke="#3E2F59" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="17" r="1.1" fill="#3E2F59"/></svg>';
export const ICONE_SELO = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="9" r="5.5" stroke="#3E2F59" stroke-width="2"/><path d="M8.5 13.5L7 21l5-2.5 5 2.5-1.5-7.5" stroke="#3E2F59" stroke-width="2" stroke-linejoin="round"/></svg>';

const dois = (n) => String(n).padStart(2, '0');
export function dataCurta(iso) {
  const d = new Date(iso);
  return `${dois(d.getDate())}/${dois(d.getMonth() + 1)}`;
}
export function dataLonga(iso) {
  const d = new Date(iso);
  return `${dataCurta(iso)}/${d.getFullYear()}`;
}
