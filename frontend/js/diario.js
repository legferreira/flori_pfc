import { chamarApi, iniciarAreaLogada } from './compartilhado/area-logada.js';
import { el, svg } from './compartilhado/dom.js';
import { abrirDiario, casoDeBloqueio, TEXTOS_BLOQUEIO } from './compartilhado/estado-diario.js';
import { confirmar, pedirConsentimentoSaude, perguntarSituacao } from './compartilhado/saude.js';

const FUSO = 'America/Sao_Paulo';
const MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const DIAS_DA_SEMANA = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
const PESO = { leve: 1, medio: 2, intenso: 3 };
const painel = document.getElementById('painel');

const estado = { ano: 0, mes: 0, registros: new Map(), resumo: null, opcoes: null, sintomas: [] };

const hoje = () => new Date().toLocaleDateString('en-CA', { timeZone: FUSO });
const doisDigitos = (n) => String(n).padStart(2, '0');
const isoDoDia = (ano, mes, dia) => `${ano}-${doisDigitos(mes)}-${doisDigitos(dia)}`;
const chaveDoMes = (ano, mes) => ano * 12 + mes;

function dataPorExtenso(iso, comAno = true) {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString('pt-BR', {
    timeZone: 'UTC', day: 'numeric', month: 'long', ...(comAno ? { year: 'numeric' } : {}), weekday: comAno ? 'long' : undefined,
  });
}

function diaMes(iso) {
  const [, mes, dia] = iso.split('-');
  return `${dia}/${mes}`;
}

function rotulo(grupo, codigo) {
  return (estado.opcoes?.[grupo] || []).find((o) => o.codigo === codigo)?.rotulo || codigo;
}

function gota({ intensidade, prevista = false, tamanho = 14 }) {
  const desenho = svg('svg', { width: tamanho, height: tamanho, viewBox: '0 0 16 16', 'aria-hidden': 'true', class: `flori-gota ${prevista ? 'is-prevista' : `is-${intensidade}`}` },
    svg('path', { d: 'M8 1.5C8 1.5 3 7.2 3 10.2a5 5 0 0 0 10 0C13 7.2 8 1.5 8 1.5z' }));
  return desenho;
}

function rosto(humor, tamanho = 16) {
  const bocas = {
    triste: 'M8.5 16.5c1-1.6 6-1.6 7 0',
    cansada: 'M9 15.5h6',
    normal: 'M9 15c1 .8 5 .8 6 0',
    animada: 'M8 13.5c1 3.2 7 3.2 8 0z',
  };
  const olhos = humor === 'cansada'
    ? [svg('path', { d: 'M8 10h2.4M13.6 10H16', 'stroke-linecap': 'round' })]
    : [svg('circle', { cx: 9.2, cy: 10, r: 1.1, class: 'flori-rosto-olho' }), svg('circle', { cx: 14.8, cy: 10, r: 1.1, class: 'flori-rosto-olho' })];
  return svg('svg', { width: tamanho, height: tamanho, viewBox: '0 0 24 24', 'aria-hidden': 'true', class: `flori-rosto is-${humor}` },
    svg('circle', { cx: 12, cy: 12, r: 10 }), ...olhos,
    svg('path', { d: bocas[humor], 'stroke-linecap': 'round', class: humor === 'animada' ? 'flori-rosto-sorriso' : '' }));
}

function descricaoDoDia(iso, registro, prevista) {
  const partes = [dataPorExtenso(iso, false)];
  if (iso === hoje()) partes.push('hoje');
  if (registro?.fluxo) partes.push(`menstruação: ${rotulo('fluxo', registro.fluxo).toLowerCase()}`);
  if (registro?.humor) partes.push(`humor: ${rotulo('humor', registro.humor).toLowerCase()}`);
  if (registro?.sintomas.length) {
    partes.push(`sintomas: ${registro.sintomas.map((s) => `${s.nome.toLowerCase()} ${rotulo('intensidade', s.intensidade).toLowerCase()}`).join(', ')}`);
  }
  if (prevista) partes.push('menstruação prevista');
  return partes.join(', ');
}

function juntar(lista) {
  if (lista.length <= 1) return lista.join('');
  return `${lista.slice(0, -1).join(', ')} e ${lista[lista.length - 1]}`;
}

function cartaoResumo(r) {
  const frases = [];
  if (r.duracao.status === 'ok') {
    frases.push(`Seu ciclo costuma durar cerca de ${r.duracao.media_dias} dias.`);
    if (r.atrasada) {
      frases.push(`Sua menstruação estava prevista para ${diaMes(r.proxima_data)}. Registre quando ela vier para atualizar o resumo.`);
    } else {
      frases.push(`Sua próxima menstruação deve vir por volta de ${diaMes(r.proxima_data)}.`);
    }
    if (r.dia_do_ciclo) frases.push(`Hoje é o dia ${r.dia_do_ciclo} do seu ciclo.`);
  } else {
    frases.push('Estamos aprendendo a calcular o seu ciclo. Registre pelo menos três inícios de menstruação.');
  }
  if (r.fluxo_mais_frequente) frases.push(`Seu fluxo costuma ser ${rotulo('fluxo', r.fluxo_mais_frequente).toLowerCase()}.`);
  if (r.humor_mais_frequente) frases.push(`Seu humor costuma ser ${rotulo('humor', r.humor_mais_frequente).toLowerCase()}.`);
  if (r.sintomas_mais_frequentes.length) {
    const sintomas = r.sintomas_mais_frequentes.map((s) => `${s.nome.toLowerCase()} (${rotulo('intensidade', s.intensidade).toLowerCase()})`);
    frases.push(`Seus sintomas mais comuns: ${juntar(sintomas)}.`);
  }
  return el('section', { class: 'flori-card flori-diario-resumo', 'aria-labelledby': 'tituloResumo' },
    el('h2', { class: 'flori-heading', id: 'tituloResumo', text: 'Resumo do ciclo' }),
    el('ul', { class: 'flori-diario-frases' }, frases.map((f) => el('li', { text: f }))),
    r.orientacao ? el('p', { class: 'flori-diario-orientacao', text: r.orientacao }) : null,
    el('p', { class: 'flori-diario-aviso', text: r.aviso }));
}

function limiteDoCalendario() {
  const [ano, mes] = hoje().split('-').map(Number);
  let limite = chaveDoMes(ano, mes);
  if (estado.resumo?.proxima_data) {
    const [pa, pm] = estado.resumo.proxima_data.split('-').map(Number);
    limite = Math.max(limite, chaveDoMes(pa, pm));
  }
  return limite;
}

function filtro() {
  const [anoAtual, mesAtual] = hoje().split('-').map(Number);
  const limite = limiteDoCalendario();
  const anos = [];
  for (let a = anoAtual - 5; a <= anoAtual; a += 1) anos.push(a);
  if (Math.floor((limite - 1) / 12) > anoAtual) anos.push(anoAtual + 1);
  const seletorMes = el('select', { class: 'form-select', id: 'filtroMes' },
    MESES.map((nome, i) => el('option', { value: i + 1, text: nome, disabled: chaveDoMes(estado.ano, i + 1) > limite })));
  seletorMes.value = String(estado.mes);
  const seletorAno = el('select', { class: 'form-select', id: 'filtroAno' }, anos.map((a) => el('option', { value: a, text: String(a) })));
  seletorAno.value = String(estado.ano);
  const ir = (ano, mes) => {
    const chave = Math.min(Math.max(chaveDoMes(ano, mes), chaveDoMes(anoAtual - 5, 1)), limite);
    estado.ano = Math.floor((chave - 1) / 12);
    estado.mes = chave - estado.ano * 12;
    carregarMes();
  };
  seletorMes.addEventListener('change', () => ir(estado.ano, Number(seletorMes.value)));
  seletorAno.addEventListener('change', () => ir(Number(seletorAno.value), estado.mes));
  const atual = chaveDoMes(estado.ano, estado.mes);
  return el('div', { class: 'flori-diario-filtro' },
    el('button', {
      type: 'button', class: 'btn btn-flori-outline btn-flori-sm', 'aria-label': 'Mês anterior', text: '‹',
      disabled: atual <= chaveDoMes(anoAtual - 5, 1), onclick: () => ir(estado.ano, estado.mes - 1),
    }),
    el('label', { class: 'visually-hidden', for: 'filtroMes', text: 'Mês' }), seletorMes,
    el('label', { class: 'visually-hidden', for: 'filtroAno', text: 'Ano' }), seletorAno,
    el('button', {
      type: 'button', class: 'btn btn-flori-outline btn-flori-sm', 'aria-label': 'Próximo mês', text: '›',
      disabled: atual >= limite, onclick: () => ir(estado.ano, estado.mes + 1),
    }),
    el('button', { type: 'button', class: 'btn btn-flori btn-flori-sm', text: 'Hoje', onclick: () => ir(anoAtual, mesAtual) }));
}

function maiorIntensidade(sintomas) {
  return sintomas.reduce((maior, s) => (PESO[s.intensidade] > PESO[maior] ? s.intensidade : maior), 'leve');
}

function calendario() {
  const hojeIso = hoje();
  const prevista = estado.resumo?.proxima_data;
  const primeiro = new Date(Date.UTC(estado.ano, estado.mes - 1, 1));
  const totalDias = new Date(Date.UTC(estado.ano, estado.mes, 0)).getUTCDate();
  const celulas = [];
  for (let i = 0; i < primeiro.getUTCDay(); i += 1) celulas.push(el('span', { class: 'flori-dia is-vazio', 'aria-hidden': 'true' }));
  for (let dia = 1; dia <= totalDias; dia += 1) {
    const iso = isoDoDia(estado.ano, estado.mes, dia);
    const registro = estado.registros.get(iso);
    const ePrevista = iso === prevista;
    const futuro = iso > hojeIso;
    const marcadores = el('span', { class: 'flori-dia-marcas' },
      registro?.fluxo && registro.fluxo !== 'sem_fluxo' ? gota({ intensidade: registro.fluxo }) : null,
      registro?.humor ? rosto(registro.humor) : null,
      registro?.sintomas.length ? el('span', { class: `flori-ponto is-${maiorIntensidade(registro.sintomas)}`, 'aria-hidden': 'true' }) : null,
      ePrevista ? el('span', { class: 'flori-prevista' }, gota({ prevista: true }), el('span', { text: 'prevista' })) : null);
    const descricao = descricaoDoDia(iso, registro, ePrevista);
    celulas.push(el('button', {
      type: 'button', class: `flori-dia${iso === hojeIso ? ' is-hoje' : ''}${registro ? ' is-registrado' : ''}`,
      disabled: futuro, 'aria-label': descricao, title: descricao, 'aria-current': iso === hojeIso ? 'date' : undefined,
      onclick: () => abrirDia(iso),
    }, el('span', { class: 'flori-dia-numero', text: String(dia) }), marcadores));
  }
  return el('section', { class: 'flori-card flori-diario-calendario', 'aria-label': `Calendário de ${MESES[estado.mes - 1]} de ${estado.ano}` },
    el('div', { class: 'flori-calendario', role: 'group' },
      DIAS_DA_SEMANA.map((d) => el('span', { class: 'flori-dia-semana', 'aria-hidden': 'true', text: d })),
      celulas),
    el('ul', { class: 'flori-diario-legenda' },
      el('li', {}, gota({ intensidade: 'medio' }), 'menstruação'),
      el('li', {}, rosto('normal'), 'humor'),
      el('li', {}, el('span', { class: 'flori-ponto is-medio', 'aria-hidden': 'true' }), 'sintomas'),
      el('li', {}, gota({ prevista: true }), 'menstruação prevista')));
}

function botaoApagarTudo() {
  return el('button', {
    type: 'button', class: 'btn flori-btn-perigo-contorno flori-diario-apagar', text: 'Apagar todo o meu diário',
    onclick: async () => {
      const sim = await confirmar({
        titulo: 'Apagar todo o seu diário?',
        texto: 'Todos os registros de menstruação, humor e sintomas serão apagados para sempre. Isso não pode ser desfeito.',
        rotulo: 'Apagar tudo', perigo: true,
      });
      if (!sim) return;
      const { ok } = await chamarApi('/diario', { metodo: 'DELETE', corpo: { confirmar: true } });
      if (ok) carregar();
    },
  });
}

function desenharDiario() {
  painel.replaceChildren(cartaoResumo(estado.resumo), filtro(), calendario(), botaoApagarTudo());
}

async function carregarMes() {
  const [anoAtual, mesAtual] = hoje().split('-').map(Number);
  estado.registros = new Map();
  if (chaveDoMes(estado.ano, estado.mes) <= chaveDoMes(anoAtual, mesAtual)) {
    const { ok, dados } = await chamarApi(`/diario?mes=${estado.ano}-${doisDigitos(estado.mes)}`);
    if (!ok) { mostrarErro(dados.mensagem); return; }
    estado.registros = new Map(dados.registros.map((r) => [r.data, r]));
    estado.sintomas = dados.sintomas;
    estado.opcoes = dados.opcoes;
  }
  desenharDiario();
}

function mostrarErro(mensagem) {
  painel.replaceChildren(el('div', { class: 'flori-card text-center' },
    el('p', { class: 'mb-3', text: mensagem || 'Não foi possível carregar o diário.' }),
    el('button', { type: 'button', class: 'btn btn-flori btn-flori-sm', text: 'Tentar de novo', onclick: carregar })));
}

function telaSemConsentimento() {
  painel.replaceChildren(el('section', { class: 'flori-card flori-diario-aviso-card' },
    el('h2', { class: 'flori-heading', text: 'Precisamos da sua permissão' }),
    el('p', { text: 'Para usar o diário do corpo, aceite o consentimento de dados de saúde. Seus registros ficam guardados e só você vê.' }),
    el('div', { class: 'flori-saude-acoes' },
      el('button', {
        type: 'button', class: 'btn btn-flori', text: 'Ver e aceitar',
        onclick: async () => { if (await pedirConsentimentoSaude()) carregar(); },
      }),
      botaoApagarTudo())));
}

function telaBloqueada(caso) {
  const { texto, botao } = TEXTOS_BLOQUEIO[caso];
  painel.replaceChildren(el('section', { class: 'flori-card flori-diario-aviso-card' },
    el('p', { text: texto }),
    el('button', { type: 'button', class: 'btn btn-flori', text: botao, onclick: responderSituacao })));
}

async function responderSituacao() {
  const novo = await perguntarSituacao({ temConsentimento: Boolean(perfil.consentimento_saude?.aceito), podeAdiar: false });
  if (!novo) return;
  Object.assign(perfil, {
    situacao_menstrual: novo.situacao,
    diario_disponivel: novo.diario_disponivel,
    consentimento_saude: { ...(perfil.consentimento_saude || {}), aceito: novo.consentimento_saude },
  });
  abrir();
}

function telaAdmin() {
  painel.replaceChildren(el('p', { class: 'flori-hint', text: 'O diário do corpo é pessoal e não fica disponível para o perfil admin.' }));
}

function abrir() {
  abrirDiario(perfil, { carregarDiario: carregar, mostrarBloqueio: telaBloqueada, mostrarAdmin: telaAdmin });
}

async function carregar() {
  painel.replaceChildren(el('p', { class: 'flori-hint', role: 'status', text: 'Carregando o seu diário...' }));
  try {
    const { ok, dados: situacao } = await chamarApi('/diario/situacao');
    if (!ok) { mostrarErro(situacao.mensagem); return; }
    if (!situacao.consentimento_saude) { telaSemConsentimento(); return; }
    if (!situacao.diario_disponivel) { telaBloqueada(casoDeBloqueio(situacao.situacao)); return; }
    const resumo = await chamarApi('/diario/resumo');
    if (!resumo.ok) { mostrarErro(resumo.dados.mensagem); return; }
    estado.resumo = resumo.dados;
    if (!estado.ano) [estado.ano, estado.mes] = hoje().split('-').map(Number);
    await carregarMes();
  } catch {
    mostrarErro('Sem conexão com o servidor.');
  }
}

function grupoDeOpcoes({ nome, legenda, opcoes, marcado, desenhoDe, erroId }) {
  const erro = el('small', { class: 'flori-erro-campo', id: erroId, hidden: true });
  const itens = opcoes.map((o) => {
    const entrada = el('input', { type: 'radio', name: nome, value: o.codigo, class: 'visually-hidden', checked: marcado === o.codigo });
    entrada.addEventListener('click', () => {
      if (entrada.dataset.marcado === '1') {
        entrada.checked = false;
        entrada.dataset.marcado = '';
      } else {
        document.querySelectorAll(`input[name="${nome}"]`).forEach((r) => { r.dataset.marcado = ''; });
        entrada.dataset.marcado = '1';
      }
    });
    if (marcado === o.codigo) entrada.dataset.marcado = '1';
    return el('label', { class: 'flori-escolha' }, entrada, desenhoDe ? desenhoDe(o.codigo) : null, el('span', { text: o.rotulo }));
  });
  return {
    bloco: el('fieldset', { class: 'flori-dia-grupo', 'aria-describedby': erroId }, el('legend', { text: legenda }),
      el('div', { class: 'flori-escolhas' }, itens), erro),
    erro,
  };
}

function abrirDia(iso) {
  const registro = estado.registros.get(iso);
  const atuais = new Map((registro?.sintomas || []).map((s) => [s.codigo, s.intensidade]));
  const fluxo = grupoDeOpcoes({
    nome: 'diaFluxo', legenda: 'Menstruação', opcoes: estado.opcoes.fluxo, marcado: registro?.fluxo, erroId: 'erroFluxo',
    desenhoDe: (c) => (c === 'sem_fluxo' ? null : gota({ intensidade: c, tamanho: 18 })),
  });
  const humor = grupoDeOpcoes({
    nome: 'diaHumor', legenda: 'Humor', opcoes: estado.opcoes.humor, marcado: registro?.humor, erroId: 'erroHumor',
    desenhoDe: (c) => rosto(c, 30),
  });
  const erroSintomas = el('small', { class: 'flori-erro-campo', id: 'erroSintomas', hidden: true });
  const linhas = estado.sintomas.map((s) => el('div', { class: 'flori-sintoma', role: 'radiogroup', 'aria-label': s.nome },
    el('span', { class: 'flori-sintoma-nome', text: s.nome }),
    el('span', { class: 'flori-sintoma-opcoes' }, estado.opcoes.intensidade.map((o) => el('label', { class: 'flori-escolha flori-escolha-compacta' },
      el('input', {
        type: 'radio', name: `sintoma_${s.codigo}`, value: o.codigo, class: 'visually-hidden',
        checked: (atuais.get(s.codigo) || 'nenhum') === o.codigo,
      }),
      el('span', { text: o.rotulo }))))));
  const geral = el('p', { class: 'flori-error', role: 'alert', hidden: true });
  const salvar = el('button', { type: 'submit', class: 'btn btn-flori', text: 'Salvar' });
  const dialogo = el('dialog', { class: 'flori-modal flori-dia-modal', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'tituloDia' });
  const form = el('form', { novalidate: true },
    el('h2', { class: 'flori-heading h4', id: 'tituloDia', text: dataPorExtenso(iso) }),
    geral, fluxo.bloco, humor.bloco,
    el('fieldset', { class: 'flori-dia-grupo', 'aria-describedby': 'erroSintomas' }, el('legend', { text: 'Sintomas' }),
      el('div', { class: 'flori-sintomas' }, linhas), erroSintomas),
    el('div', { class: 'flori-saude-acoes' },
      registro ? el('button', {
        type: 'button', class: 'btn flori-btn-perigo-contorno flori-dia-excluir', text: 'Excluir registro',
        onclick: async () => {
          const { ok } = await chamarApi(`/diario/${iso}`, { metodo: 'DELETE' });
          if (ok) { dialogo.close(); recarregarDepoisDeSalvar(); }
        },
      }) : null,
      el('button', { type: 'button', class: 'btn btn-flori-outline', text: 'Cancelar', onclick: () => dialogo.close() }),
      salvar));
  const mostrar = (elemento, texto) => { elemento.textContent = texto || ''; elemento.hidden = !texto; };
  form.addEventListener('submit', async (evento) => {
    evento.preventDefault();
    [geral, fluxo.erro, humor.erro, erroSintomas].forEach((e) => mostrar(e, ''));
    const corpo = {
      fluxo: form.querySelector('input[name="diaFluxo"]:checked')?.value || null,
      humor: form.querySelector('input[name="diaHumor"]:checked')?.value || null,
      sintomas: estado.sintomas
        .map((s) => ({ codigo: s.codigo, intensidade: form.querySelector(`input[name="sintoma_${s.codigo}"]:checked`)?.value }))
        .filter((s) => s.intensidade && s.intensidade !== 'nenhum'),
    };
    if (!corpo.fluxo && !corpo.humor && !corpo.sintomas.length) {
      mostrar(geral, 'Escolha pelo menos a menstruação, o humor ou um sintoma.');
      return;
    }
    salvar.disabled = true;
    salvar.textContent = 'Salvando...';
    const { ok, dados } = await chamarApi(`/diario/${iso}`, { metodo: 'PUT', corpo });
    salvar.disabled = false;
    salvar.textContent = 'Salvar';
    if (!ok) {
      const campos = dados.campos || {};
      if (campos.fluxo) mostrar(fluxo.erro, campos.fluxo);
      if (campos.humor) mostrar(humor.erro, campos.humor);
      const deSintomas = Object.entries(campos).filter(([k]) => k.startsWith('sintomas')).map(([, v]) => v);
      if (deSintomas.length) mostrar(erroSintomas, deSintomas.join(' '));
      if (!campos.fluxo && !campos.humor && !deSintomas.length) mostrar(geral, campos.registro || campos.data || dados.mensagem);
      return;
    }
    dialogo.close();
    recarregarDepoisDeSalvar();
  });
  dialogo.append(form);
  document.body.append(dialogo);
  dialogo.addEventListener('close', () => dialogo.remove());
  dialogo.showModal();
  form.querySelector('input')?.focus();
}

async function recarregarDepoisDeSalvar() {
  const resumo = await chamarApi('/diario/resumo');
  if (resumo.ok) estado.resumo = resumo.dados;
  await carregarMes();
}

window.addEventListener('flori:situacao', abrir);

const perfil = await iniciarAreaLogada('diario');
abrir();
