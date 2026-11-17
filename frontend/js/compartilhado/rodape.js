export const LINKS_DO_RODAPE = [
  { href: 'termos-de-uso.html', texto: 'Termos de uso' },
  { href: 'politica-privacidade.html', texto: 'Política de privacidade' },
];

export function criarRodape(documento = document, { classeExtra = '' } = {}) {
  const rodape = documento.createElement('footer');
  rodape.className = classeExtra ? `flori-rodape ${classeExtra}` : 'flori-rodape';
  for (const { href, texto } of LINKS_DO_RODAPE) {
    const link = documento.createElement('a');
    link.setAttribute('href', href);
    link.setAttribute('target', '_blank');
    link.setAttribute('rel', 'noopener');
    link.textContent = texto;
    rodape.append(link);
  }
  return rodape;
}

export function desenharRodape({ destino = document.body, classeExtra = '' } = {}) {
  if (document.querySelector('footer.flori-rodape')) return;
  destino.append(criarRodape(document, { classeExtra }));
}
