import { chamarApi } from '../compartilhado/area-logada.js';
import { botao, chip, el, estadoCarregando, estadoErro, toast } from './interface.js';

const FUSO = 'America/Sao_Paulo';
const LIMITE_OBSERVACAO = 140;
const SITUACOES = [['ativas', 'Ativas'], ['excluidas', 'Excluídas'], ['todas', 'Todas']];
const ORDENS = [['cadastro_desc', 'Cadastro mais recente'], ['cadastro_asc', 'Cadastro mais antigo'], ['entrada_desc', 'Última entrada']];
const QUIZ = {
  aprovada: ['aprovada', 'is-ativo'],
  nao_aprovada: ['não aprovada', 'is-alerta'],
  nao_tentou: ['não tentou', ''],
};

const estado = { busca: '', situacao: 'ativas', ordem: 'cadastro_desc', pagina: 1, area: null, pedido: 0, alvo: null };
let temporizadorBusca = null;

const modal = document.getElementById('modalExcluirUser');
const form = document.getElementById('formExcluirUser');
const motivo = document.getElementById('motivoExcluir');
const observacao = document.getElementById('observacaoExcluir');
const contador = document.getElementById('observacaoExcluir_contador');
const erroMotivo = document.getElementById('motivoExcluir_erro');
const erroObservacao = document.getElementById('observacaoExcluir_erro');
const erroGeral = document.getElementById('erroExcluirUser');
const botaoConfirmar = document.getElementById('botaoExcluirUser');

function diaEmSaoPaulo(data) {
  return data.toLocaleDateString('pt-BR', { timeZone: FUSO, day: '2-digit', month: '2-digit', year: 'numeric' });
}

function horaEmSaoPaulo(data) {
  return data.toLocaleTimeString('pt-BR', { timeZone: FUSO, hour: '2-digit', minute: '2-digit', hour12: false });
}

function ultimaEntrada(iso) {
  const data = new Date(iso);
  const hoje = new Date();
  const ontem = new Date(hoje.getTime() - 24 * 60 * 60 * 1000);
  if (diaEmSaoPaulo(data) === diaEmSaoPaulo(hoje)) return `hoje, ${horaEmSaoPaulo(data)}`;
  if (diaEmSaoPaulo(data) === diaEmSaoPaulo(ontem)) return `ontem, ${horaEmSaoPaulo(data)}`;
  return diaEmSaoPaulo(data);
}

function semDado() {
  return el('span', {}, el('span', { 'aria-hidden': 'true', text: '–' }), el('span', { class: 'visually-hidden', text: 'sem dado' }));
}

function soVisualiza() {
  return el('span', { class: 'flori-hint', text: 'só visualiza' });
}

function celulaTrilha(conta) {
  if (conta.perfil === 'admin') return soVisualiza();
  if (!conta.trilha) return semDado();
  const { concluidos, total } = conta.trilha;
  const largura = total ? Math.round((concluidos / total) * 100) : 0;
  const barra = el('span', { class: 'flori-us-barra', 'aria-hidden': 'true' }, el('span'));
  barra.firstChild.style.width = `${largura}%`;
  return el('span', { class: 'flori-us-trilha' }, el('span', { text: `${concluidos} de ${total}` }), barra);
}

function celulaQuiz(conta) {
  if (conta.perfil === 'admin') return soVisualiza();
  if (!conta.quiz) return semDado();
  const [texto, tipo] = QUIZ[conta.quiz];
  return chip(texto, tipo);
}

function celulaAcao(conta) {
  if (conta.situacao === 'excluida') {
    return el('span', { class: 'flori-hint flori-us-excluida' },
      el('span', { text: 'Conta excluída' }),
      conta.excluida_em ? el('small', { text: diaEmSaoPaulo(new Date(conta.excluida_em)) }) : null);
  }
  if (conta.perfil === 'admin') return el('span', { class: 'flori-hint', text: 'Conta protegida' });
  return botao('Excluir', {
    'aria-label': `Excluir a conta de ${conta.apelido}`, 'data-foco': `excluir:${conta.id}`,
    onclick: () => abrirExclusao(conta),
  }, 'perigo');
}

function linha(conta) {
  const excluida = conta.situacao === 'excluida';
  const celulas = [
    el('span', { class: 'flori-us-apelido' }, el('span', { text: conta.apelido }), conta.demo ? chip('demo') : null),
    conta.email_mascarado ? el('span', { text: conta.email_mascarado }) : semDado(),
    el('span', { text: diaEmSaoPaulo(new Date(conta.cadastro)) }),
    conta.perfil === 'admin' ? el('span', { class: 'flori-selo flori-selo-admin', text: 'admin' }) : el('span', { text: 'user' }),
    celulaTrilha(conta),
    celulaQuiz(conta),
    conta.ultima_entrada ? el('span', { text: ultimaEntrada(conta.ultima_entrada) }) : semDado(),
    excluida ? chip('excluída') : chip('ativa', 'is-ativo'),
    celulaAcao(conta),
  ];
  return el('tr', { class: excluida ? 'flori-us-linha-excluida' : '' },
    celulas.map((conteudo, i) => el('td', { class: i === celulas.length - 1 ? 'flori-acoes' : '' }, conteudo)));
}

function rodape(dados) {
  const inicio = dados.total ? (dados.pagina - 1) * dados.por_pagina + 1 : 0;
  const fim = Math.min(dados.pagina * dados.por_pagina, dados.total);
  const ir = (pagina) => { estado.pagina = pagina; carregar(); };
  return el('div', { class: 'flori-paginacao' },
    el('span', { text: `Mostrando ${inicio} a ${fim} de ${dados.total} ${dados.total === 1 ? 'conta' : 'contas'}` }),
    el('div', { class: 'flori-ct-acoes' },
      botao('Anterior', { disabled: dados.pagina <= 1, onclick: () => ir(dados.pagina - 1) }),
      botao('Próxima', { disabled: dados.pagina >= dados.total_paginas, onclick: () => ir(dados.pagina + 1) })));
}

function tabela(dados) {
  const titulos = ['Apelido', 'E-mail', 'Cadastro', 'Perfil', 'Trilha', 'Quiz', 'Última entrada', 'Situação'];
  return el('div', {},
    el('div', { class: 'flori-tabela-caixa' },
      el('table', { class: 'flori-tabela flori-us-tabela' },
        el('thead', {}, el('tr', {},
          titulos.map((t) => el('th', { scope: 'col', text: t })),
          el('th', { scope: 'col' }, el('span', { class: 'visually-hidden', text: 'Ação' })))),
        el('tbody', {}, dados.itens.map(linha)))),
    rodape(dados));
}

async function carregar() {
  const numero = ++estado.pedido;
  const consulta = new URLSearchParams({ situacao: estado.situacao, ordem: estado.ordem, pagina: String(estado.pagina) });
  if (estado.busca) consulta.set('busca', estado.busca);
  estado.area.replaceChildren(estadoCarregando('Carregando contas...'));
  let resposta;
  try {
    resposta = await chamarApi(`/admin/users?${consulta}`);
  } catch {
    resposta = { ok: false, dados: {} };
  }
  if (numero !== estado.pedido) return;
  if (!resposta.ok) {
    estado.area.replaceChildren(estadoErro(resposta.dados.mensagem || 'Não foi possível carregar as contas.', carregar));
    return;
  }
  const dados = resposta.dados;
  if (!dados.itens.length && dados.pagina > 1 && dados.total) {
    estado.pagina = dados.total_paginas;
    carregar();
    return;
  }
  estado.area.replaceChildren(dados.itens.length
    ? tabela(dados)
    : el('div', { class: 'flori-ct-vazio' }, el('p', { class: 'mb-0', text: 'Nenhuma conta encontrada.' })));
}

function seletor(id, rotulo, opcoes, valor, aoMudar) {
  const select = el('select', { class: 'form-select', id },
    opcoes.map(([chave, texto]) => el('option', { value: chave, text: texto })));
  select.value = valor;
  select.addEventListener('change', () => aoMudar(select.value));
  return el('div', {}, el('label', { class: 'form-label', for: id, text: rotulo }), select);
}

export function desenharUsuarios(painel) {
  const busca = el('input', {
    type: 'search', class: 'form-control', id: 'buscaApelido', maxlength: 50, autocomplete: 'off', value: estado.busca,
  });
  busca.addEventListener('input', () => {
    clearTimeout(temporizadorBusca);
    temporizadorBusca = setTimeout(() => {
      estado.busca = busca.value.trim();
      estado.pagina = 1;
      carregar();
    }, 300);
  });
  const filtros = el('div', { class: 'flori-filtros', role: 'search' },
    el('div', {}, el('label', { class: 'form-label', for: 'buscaApelido', text: 'Buscar por apelido' }), busca),
    seletor('filtroSituacao', 'Situação', SITUACOES, estado.situacao, (valor) => {
      estado.situacao = valor;
      estado.pagina = 1;
      carregar();
    }),
    seletor('filtroOrdem', 'Ordenar por', ORDENS, estado.ordem, (valor) => {
      estado.ordem = valor;
      estado.pagina = 1;
      carregar();
    }));
  estado.area = el('div', { 'aria-live': 'polite' });
  painel.replaceChildren(el('section', { class: 'flori-painel flori-us' },
    filtros,
    el('p', {
      class: 'flori-ct-aviso',
      text: 'O e-mail aparece mascarado. O admin não edita dados pessoais. A única ação sobre uma conta é a exclusão, que fica registrada.',
    }),
    estado.area));
  carregar();
}

function mostrarErro(campo, elemento, mensagem) {
  elemento.textContent = mensagem || '';
  elemento.hidden = !mensagem;
  if (mensagem) campo.setAttribute('aria-invalid', 'true');
  else campo.removeAttribute('aria-invalid');
}

function limparErros() {
  mostrarErro(motivo, erroMotivo, '');
  mostrarErro(observacao, erroObservacao, '');
  erroGeral.textContent = '';
  erroGeral.hidden = true;
}

function atualizarContador() {
  contador.textContent = `${observacao.value.length} de ${LIMITE_OBSERVACAO}`;
}

function abrirExclusao(conta) {
  estado.alvo = conta;
  form.reset();
  limparErros();
  atualizarContador();
  document.getElementById('descricaoExcluirUser').textContent = `Conta de ${conta.apelido}.`;
  botaoConfirmar.disabled = false;
  botaoConfirmar.textContent = 'Excluir conta';
  modal.showModal();
  motivo.focus();
}

observacao.addEventListener('input', atualizarContador);

form.addEventListener('submit', async (evento) => {
  evento.preventDefault();
  limparErros();
  if (!motivo.value) {
    mostrarErro(motivo, erroMotivo, 'Escolha um motivo.');
    motivo.focus();
    return;
  }
  botaoConfirmar.disabled = true;
  botaoConfirmar.textContent = 'Excluindo...';
  let resposta;
  try {
    resposta = await chamarApi(`/admin/users/${estado.alvo.id}/excluir`, {
      metodo: 'POST', corpo: { motivo: motivo.value, observacao: observacao.value.trim() },
    });
  } catch {
    resposta = { ok: false, dados: { mensagem: 'Sem conexão com o servidor.' } };
  }
  botaoConfirmar.disabled = false;
  botaoConfirmar.textContent = 'Excluir conta';
  if (!resposta.ok) {
    const campos = resposta.dados.campos || {};
    if (campos.motivo) mostrarErro(motivo, erroMotivo, campos.motivo);
    if (campos.observacao) mostrarErro(observacao, erroObservacao, campos.observacao);
    if (!campos.motivo && !campos.observacao) {
      erroGeral.textContent = resposta.dados.mensagem || 'Não foi possível excluir a conta.';
      erroGeral.hidden = false;
    }
    return;
  }
  modal.close();
  toast('Conta excluída');
  carregar();
});
