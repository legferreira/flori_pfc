import { chamarApi } from '../compartilhado/area-logada.js';
import { botao, el, estadoCarregando, estadoErro } from './interface.js';

const SVG = 'http://www.w3.org/2000/svg';
const FUSO = 'America/Sao_Paulo';
const DIAS_PADRAO = 30;
const DIAS_MAXIMO = 366;
const CORES_ASSUNTO = ['var(--vg-rosa)', 'var(--vg-verde)', 'var(--vg-lilas)'];
const ETAPAS = [
  ['entraram', 'Entraram no período', 'entraram no período'],
  ['iniciaram_trilha', 'Iniciaram a trilha', 'iniciaram a trilha'],
  ['concluiram_cards', 'Concluíram os cards', 'concluíram os cards'],
  ['tentaram_quiz', 'Tentaram o quiz', 'tentaram o quiz'],
  ['aprovadas_quiz', 'Aprovadas no quiz', 'foram aprovadas no quiz'],
];
const SITUACOES = {
  concluiram: ['Concluíram a trilha', 'var(--vg-verde)'],
  em_andamento: ['Em andamento', 'var(--vg-rosa)'],
  nao_iniciaram: ['Não iniciaram', 'var(--vg-lilas)'],
};

let periodo = null;

const plural = (n, singular, pluralTexto) => `${n} ${n === 1 ? singular : pluralTexto}`;
const contas = (n) => plural(n, 'conta', 'contas');
const decimal = (n) => n.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

function hojeEmSaoPaulo() {
  return new Date().toLocaleDateString('en-CA', { timeZone: FUSO });
}

function somarDias(iso, dias) {
  const data = new Date(`${iso}T12:00:00Z`);
  data.setUTCDate(data.getUTCDate() + dias);
  return data.toISOString().slice(0, 10);
}

function diasEntre(de, ate) {
  return Math.round((new Date(`${ate}T12:00:00Z`) - new Date(`${de}T12:00:00Z`)) / 86400000) + 1;
}

function dica() {
  let caixa = document.getElementById('dicaVisaoGeral');
  if (!caixa) {
    caixa = el('div', { class: 'flori-vg-dica', id: 'dicaVisaoGeral', role: 'tooltip', hidden: true });
    document.body.append(caixa);
  }
  return caixa;
}

function comDica(elemento, texto) {
  elemento.setAttribute('tabindex', '0');
  elemento.setAttribute('aria-label', texto);
  const mostrar = () => {
    const caixa = dica();
    caixa.textContent = texto;
    caixa.hidden = false;
    const area = elemento.getBoundingClientRect();
    const largura = caixa.offsetWidth;
    caixa.style.left = `${Math.max(8, Math.min(window.innerWidth - largura - 8, area.left + area.width / 2 - largura / 2))}px`;
    caixa.style.top = `${Math.max(8, area.top - caixa.offsetHeight - 8)}px`;
  };
  const esconder = () => { dica().hidden = true; };
  elemento.addEventListener('mouseenter', mostrar);
  elemento.addEventListener('focus', mostrar);
  elemento.addEventListener('mouseleave', esconder);
  elemento.addEventListener('blur', esconder);
  return elemento;
}

function tabelaEscondida(legenda, cabecalho, linhas) {
  return el('table', { class: 'visually-hidden' },
    el('caption', { text: legenda }),
    el('thead', {}, el('tr', {}, cabecalho.map((t) => el('th', { scope: 'col', text: t })))),
    el('tbody', {}, linhas.map((linha) => el('tr', {}, linha.map((c) => el('td', { text: String(c) }))))));
}

function cartao(titulo, nota, ...conteudo) {
  return el('section', { class: 'flori-vg-cartao' },
    el('h2', { class: 'flori-heading flori-vg-titulo', text: titulo }),
    el('p', { class: 'flori-vg-nota', text: nota }),
    conteudo);
}

function vazio(texto = 'Sem dados no período') {
  return el('p', { class: 'flori-vg-vazio', text: texto });
}

function indicadores(d) {
  const itens = [
    ['Cadastros no período', d.cadastros_no_periodo, d.cadastros_no_periodo === 1 ? 'nova conta' : 'novas contas'],
    ['Entraram no período', d.entraram_no_periodo, `de ${d.contas_cadastradas} ${d.contas_cadastradas === 1 ? 'conta cadastrada' : 'contas cadastradas'}`],
    ['Concluíram a trilha', d.funil.concluiram_cards, `de ${d.funil.iniciaram_trilha} que ${d.funil.iniciaram_trilha === 1 ? 'iniciou' : 'iniciaram'}`],
    ['Aprovadas no quiz', d.funil.aprovadas_quiz, `de ${d.funil.tentaram_quiz} que ${d.funil.tentaram_quiz === 1 ? 'tentou' : 'tentaram'}`],
  ];
  return el('div', { class: 'flori-vg-indicadores' }, itens.map(([rotulo, valor, detalhe]) => el('div', { class: 'flori-vg-indicador' },
    el('span', { class: 'flori-vg-indicador-rotulo', text: rotulo }),
    el('strong', { class: 'flori-vg-indicador-valor', text: String(valor) }),
    el('span', { class: 'flori-vg-indicador-detalhe', text: detalhe }))));
}

function avisos(a) {
  const excluidas = plural(a.contas_excluidas, 'conta excluída', 'contas excluídas');
  const revogados = plural(a.consentimentos_revogados, 'consentimento revogado', 'consentimentos revogados');
  return el('p', { class: 'flori-vg-avisos', text: `No período: ${excluidas} e ${revogados}.` });
}

function funil(f) {
  const base = f.entraram;
  const nota = 'Das contas que entraram no período, quantas chegaram a cada etapa';
  if (!base) return cartao('Funil da trilha', nota, vazio());
  const resumo = ETAPAS.map(([chave, rotulo]) => `${rotulo}: ${f[chave]}`).join(', ');
  const linhas = ETAPAS.map(([chave, rotulo, frase], i) => {
    const barra = el('span', { class: 'flori-vg-funil-barra' });
    barra.style.width = `${(f[chave] / base) * 100}%`;
    barra.style.background = i === ETAPAS.length - 1 ? 'var(--vg-verde)' : 'var(--vg-rosa)';
    const trilho = comDica(el('span', { class: 'flori-vg-funil-trilho' }, barra), `${contas(f[chave])} ${frase}`);
    return el('div', { class: 'flori-vg-funil-linha' },
      el('span', { class: 'flori-vg-funil-rotulo', text: rotulo }), trilho,
      el('strong', { class: 'flori-vg-funil-valor', text: String(f[chave]) }));
  });
  return cartao('Funil da trilha', nota,
    el('div', { role: 'img', 'aria-label': `Funil da trilha. ${resumo}.` }, linhas),
    tabelaEscondida('Funil da trilha', ['Etapa', 'Contas'], ETAPAS.map(([chave, rotulo]) => [rotulo, f[chave]])));
}

function rosca(situacao) {
  const nota = `Todas as ${situacao.total} contas cadastradas hoje, independente do período`;
  if (!situacao.total) return cartao('Situação das contas', nota, vazio('Nenhuma conta cadastrada ainda'));
  const raio = 48;
  const circunferencia = 2 * Math.PI * raio;
  const svg = document.createElementNS(SVG, 'svg');
  svg.setAttribute('viewBox', '0 0 120 120');
  svg.setAttribute('class', 'flori-vg-rosca');
  const fundo = document.createElementNS(SVG, 'circle');
  Object.entries({ cx: 60, cy: 60, r: raio, fill: 'none', stroke: 'var(--vg-trilho)', 'stroke-width': 16 })
    .forEach(([k, v]) => fundo.setAttribute(k, v));
  svg.append(fundo);
  let acumulado = 0;
  situacao.grupos.forEach((g) => {
    if (!g.contas) return;
    const [rotulo, cor] = SITUACOES[g.chave];
    const comprimento = (g.contas / situacao.total) * circunferencia;
    const arco = document.createElementNS(SVG, 'circle');
    Object.entries({
      cx: 60, cy: 60, r: raio, fill: 'none', stroke: cor, 'stroke-width': 16,
      'stroke-dasharray': `${comprimento} ${circunferencia - comprimento}`, 'stroke-dashoffset': -acumulado,
      transform: 'rotate(-90 60 60)', class: 'flori-vg-arco',
    }).forEach(([k, v]) => arco.setAttribute(k, v));
    comDica(arco, `${rotulo}: ${contas(g.contas)} (${decimal(g.percentual)}%)`);
    svg.append(arco);
    acumulado += comprimento;
  });
  [[56, String(situacao.total), 'flori-vg-rosca-total'], [74, 'contas', 'flori-vg-rosca-legenda']].forEach(([y, texto, classe]) => {
    const t = document.createElementNS(SVG, 'text');
    Object.entries({ x: 60, y, 'text-anchor': 'middle', class: classe }).forEach(([k, v]) => t.setAttribute(k, v));
    t.textContent = texto;
    svg.append(t);
  });
  const legenda = el('ul', { class: 'flori-vg-legenda' }, situacao.grupos.map((g) => {
    const [rotulo, cor] = SITUACOES[g.chave];
    const quadrado = el('span', { class: 'flori-vg-quadrado', 'aria-hidden': 'true' });
    quadrado.style.background = cor;
    return el('li', {}, quadrado, el('span', { text: rotulo }), el('strong', { text: String(g.contas) }),
      el('span', { class: 'flori-vg-percentual', text: `${decimal(g.percentual)}%` }));
  }));
  const resumo = situacao.grupos.map((g) => `${SITUACOES[g.chave][0]}: ${g.contas}`).join(', ');
  return cartao('Situação das contas', nota,
    el('div', { class: 'flori-vg-rosca-caixa' },
      el('div', { role: 'img', 'aria-label': `Situação das ${situacao.total} contas. ${resumo}.` }, svg),
      legenda),
    tabelaEscondida('Situação das contas', ['Situação', 'Contas', 'Percentual'],
      situacao.grupos.map((g) => [SITUACOES[g.chave][0], g.contas, `${decimal(g.percentual)}%`])));
}

function conclusaoPorCard(dados) {
  const nota = '% das contas que iniciaram a trilha, na ordem em que os cards aparecem';
  if (!dados.cards.length) return cartao('Conclusão por card', nota, vazio('Nenhum card ativo na trilha'));
  if (!dados.base) return cartao('Conclusão por card', nota, vazio('Nenhuma conta iniciou a trilha ainda'));
  const assuntos = [];
  dados.cards.forEach((c) => {
    const ultimo = assuntos[assuntos.length - 1];
    if (ultimo && ultimo.id === c.assunto_id) ultimo.cards += 1;
    else assuntos.push({ id: c.assunto_id, nome: c.assunto, cards: 1 });
  });
  const cor = (assuntoId) => CORES_ASSUNTO[assuntos.findIndex((a) => a.id === assuntoId) % CORES_ASSUNTO.length];
  const colunas = `repeat(${dados.cards.length}, minmax(28px, 1fr))`;
  const barras = el('div', { class: 'flori-vg-colunas' }, dados.cards.map((c) => {
    const barra = el('span', { class: 'flori-vg-coluna-barra' });
    barra.style.height = `${c.percentual}%`;
    barra.style.background = cor(c.assunto_id);
    return comDica(el('div', { class: 'flori-vg-coluna' },
      el('span', { class: 'flori-vg-coluna-valor', text: `${c.percentual}%` }),
      el('span', { class: 'flori-vg-coluna-trilho' }, barra),
      el('span', { class: 'flori-vg-coluna-rotulo', text: String(c.numero) })), `Card ${c.numero}, ${c.assunto}: ${c.percentual}%`);
  }));
  barras.style.gridTemplateColumns = colunas;
  const faixas = el('div', { class: 'flori-vg-faixas' }, assuntos.map((a) => {
    const faixa = el('span', { class: 'flori-vg-faixa', text: a.nome });
    faixa.style.gridColumn = `span ${a.cards}`;
    faixa.style.borderTopColor = cor(a.id);
    return faixa;
  }));
  faixas.style.gridTemplateColumns = colunas;
  const resumo = dados.cards.map((c) => `card ${c.numero}, ${c.percentual}%`).join('; ');
  return cartao('Conclusão por card', nota,
    el('div', { class: 'flori-vg-rolagem' },
      el('div', { class: 'flori-vg-grafico', role: 'img', 'aria-label': `Conclusão por card. ${resumo}.` }, barras, faixas)),
    tabelaEscondida('Conclusão por card', ['Card', 'Título', 'Assunto', 'Percentual'],
      dados.cards.map((c) => [c.numero, c.titulo, c.assunto, `${c.percentual}%`])));
}

function cadastrosPorSemana(semanas) {
  const nota = 'Novas contas em cada semana do período escolhido';
  const maximo = Math.max(0, ...semanas.map((s) => s.cadastros));
  if (!maximo) return cartao('Cadastros por semana', nota, vazio());
  const barras = el('div', { class: 'flori-vg-colunas' }, semanas.map((s) => {
    const barra = el('span', { class: 'flori-vg-coluna-barra' });
    barra.style.height = `${(s.cadastros / maximo) * 100}%`;
    barra.style.background = 'var(--vg-rosa)';
    return comDica(el('div', { class: 'flori-vg-coluna' },
      el('span', { class: 'flori-vg-coluna-valor', text: String(s.cadastros) }),
      el('span', { class: 'flori-vg-coluna-trilho' }, barra),
      el('span', { class: 'flori-vg-coluna-rotulo', text: s.rotulo })), `Semana de ${s.rotulo}: ${plural(s.cadastros, 'cadastro', 'cadastros')}`);
  }));
  barras.style.gridTemplateColumns = `repeat(${semanas.length}, minmax(40px, 1fr))`;
  const resumo = semanas.map((s) => `${s.rotulo}, ${s.cadastros}`).join('; ');
  return cartao('Cadastros por semana', nota,
    el('div', { class: 'flori-vg-rolagem' },
      el('div', { class: 'flori-vg-grafico', role: 'img', 'aria-label': `Cadastros por semana. ${resumo}.` }, barras)),
    tabelaEscondida('Cadastros por semana', ['Semana que começa em', 'Cadastros'], semanas.map((s) => [s.rotulo, s.cadastros])));
}

function desenharDados(area, d) {
  const semNada = !d.contas_cadastradas && !d.cadastros_no_periodo && !d.entraram_no_periodo;
  if (semNada) {
    area.replaceChildren(vazio());
    return;
  }
  area.replaceChildren(
    indicadores(d),
    avisos(d.avisos_periodo),
    el('div', { class: 'flori-vg-linha flori-vg-linha-larga' }, funil(d.funil), rosca(d.situacao_contas)),
    el('div', { class: 'flori-vg-linha' }, conclusaoPorCard(d.conclusao_por_card), cadastrosPorSemana(d.cadastros_por_semana)),
  );
}

async function carregar(area, campos) {
  area.replaceChildren(estadoCarregando('Carregando dados...'));
  let resposta;
  try {
    resposta = await chamarApi(`/admin/dashboard?${new URLSearchParams(periodo)}`);
  } catch {
    resposta = { ok: false, status: 0, dados: {} };
  }
  if (!resposta.ok) {
    if (resposta.status === 400 && resposta.dados.campos) {
      campos.mostrar(Object.values(resposta.dados.campos).join(' '));
      area.replaceChildren();
      return;
    }
    area.replaceChildren(estadoErro(resposta.dados.mensagem || 'Não foi possível carregar o dashboard.', () => carregar(area, campos), 'Tentar de novo'));
    return;
  }
  desenharDados(area, resposta.dados);
}

function validar(de, ate) {
  const formato = /^\d{4}-\d{2}-\d{2}$/;
  if (!formato.test(de) || !formato.test(ate) || Number.isNaN(Date.parse(de)) || Number.isNaN(Date.parse(ate))) {
    return 'Escolha datas válidas em De e Até.';
  }
  if (de > ate) return 'A data De precisa ser igual ou anterior à data Até.';
  if (diasEntre(de, ate) > DIAS_MAXIMO) return `Escolha um período de até ${DIAS_MAXIMO} dias.`;
  return '';
}

export function desenharDashboard(painel) {
  if (!periodo) {
    const ate = hojeEmSaoPaulo();
    periodo = { de: somarDias(ate, -(DIAS_PADRAO - 1)), ate };
  }
  const de = el('input', { type: 'date', class: 'form-control', id: 'periodoDe', value: periodo.de, 'aria-describedby': 'periodoErro' });
  const ate = el('input', { type: 'date', class: 'form-control', id: 'periodoAte', value: periodo.ate, 'aria-describedby': 'periodoErro' });
  const erro = el('small', { class: 'flori-ct-erro-campo', id: 'periodoErro', role: 'alert', hidden: true });
  const campos = {
    mostrar(texto) {
      erro.textContent = texto;
      erro.hidden = !texto;
      [de, ate].forEach((c) => (texto ? c.setAttribute('aria-invalid', 'true') : c.removeAttribute('aria-invalid')));
    },
  };
  const area = el('div', { 'aria-live': 'polite' });
  const form = el('form', { class: 'flori-vg-filtro', novalidate: true },
    el('span', { class: 'flori-vg-filtro-rotulo', text: 'Período' }),
    el('label', { class: 'flori-vg-campo', for: 'periodoDe' }, el('span', { text: 'De' }), de),
    el('label', { class: 'flori-vg-campo', for: 'periodoAte' }, el('span', { text: 'Até' }), ate),
    botao('Aplicar', { type: 'submit' }, 'primario'),
    erro);
  form.addEventListener('submit', (evento) => {
    evento.preventDefault();
    const mensagem = validar(de.value, ate.value);
    campos.mostrar(mensagem);
    if (mensagem) return;
    periodo = { de: de.value, ate: ate.value };
    carregar(area, campos);
  });
  painel.replaceChildren(el('div', { class: 'flori-vg' }, form, area));
  carregar(area, campos);
}
