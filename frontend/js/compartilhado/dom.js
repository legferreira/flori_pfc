const PROPRIEDADES = ['value', 'checked', 'disabled', 'hidden'];

export function el(tag, props = {}, ...filhos) {
  const no = document.createElement(tag);
  Object.entries(props).forEach(([chave, valor]) => {
    if (valor === undefined || valor === null || valor === false) return;
    if (chave === 'class') no.className = valor;
    else if (chave === 'text') no.textContent = valor;
    else if (chave === 'dataset') Object.assign(no.dataset, valor);
    else if (chave.startsWith('on')) no.addEventListener(chave.slice(2), valor);
    else if (PROPRIEDADES.includes(chave)) no[chave] = valor;
    else no.setAttribute(chave, valor === true ? '' : String(valor));
  });
  filhos.flat(Infinity).forEach((filho) => {
    if (filho === null || filho === undefined || filho === false) return;
    no.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
  });
  return no;
}

const SVG = 'http://www.w3.org/2000/svg';

export function svg(tag, atributos = {}, ...filhos) {
  const no = document.createElementNS(SVG, tag);
  Object.entries(atributos).forEach(([chave, valor]) => no.setAttribute(chave, String(valor)));
  filhos.forEach((filho) => no.append(filho));
  return no;
}
