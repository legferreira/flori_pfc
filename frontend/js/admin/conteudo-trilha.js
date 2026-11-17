import {
  SEM_CONEXAO, api, botaoSalvar, caixaExcluidos, caixaMensagem, caixaResumo, chipSituacao, editores, executarAcao,
  limparErros, mostrarFalha, mostrarMensagem, plural, previaCard, setas,
} from './conteudo-comum.js';
import {
  ICONES, botao, campoTexto, confirmar, el, estadoCarregando, estadoErro, estadoVazio, focarDepois, icone, toast,
} from './interface.js';

const LIMITES = { assunto: 100, titulo: 80, explicacao: 600, exemplo: 255, fonteNome: 120, fonteUrl: 300 };

const TIPOS = [
  {
    id: 'oficial', rotulo: 'Trilha oficial',
    ajuda: 'Cada assunto guarda os seus cards. Desativar esconde dos users e pode ser desfeito a qualquer momento. '
      + 'Excluir tira da trilha, mas o progresso já registrado é mantido.',
  },
  {
    id: 'extra', rotulo: 'Para ir além',
    ajuda: 'Conteúdos extras não contam para o quiz, para o certificado nem para os indicadores. '
      + 'Todo card daqui mostra um aviso médico fixo.',
  },
];

const estado = {
  assuntos: [], mostrarExcluidos: false, abertos: new Set(), editor: null, lista: null, mensagem: null, falha: null,
  tipo: 'oficial',
};

function seletorDeTipo(ajuda) {
  const botoes = TIPOS.map((t) => el('button', {
    type: 'button', class: 'flori-ct-segmento', 'aria-pressed': String(t.id === estado.tipo), text: t.rotulo,
    onclick: async () => {
      if (t.id === estado.tipo || !(await editores.liberar())) return;
      estado.tipo = t.id;
      botoes.forEach((b, i) => b.setAttribute('aria-pressed', String(TIPOS[i].id === t.id)));
      ajuda.textContent = t.ajuda;
      estado.lista.replaceChildren(estadoCarregando());
      carregar();
    },
  }));
  return el('div', { class: 'flori-ct-segmentado', role: 'group', 'aria-label': 'Tipo de assunto' }, botoes);
}

export async function desenharTrilha(raiz) {
  estado.editor = null;
  estado.lista = el('div', { class: 'flori-ct-lista' });
  estado.mensagem = caixaMensagem();
  const ajuda = el('p', { class: 'flori-ct-aviso', text: TIPOS.find((t) => t.id === estado.tipo).ajuda });
  raiz.replaceChildren(
    seletorDeTipo(ajuda),
    ajuda,
    el('div', { class: 'flori-ct-barra' },
      caixaExcluidos('Mostrar excluídos', estado.mostrarExcluidos, (marcado) => {
        estado.mostrarExcluidos = marcado;
        carregar();
      }),
      botao('Novo assunto', { onclick: novoAssunto, 'data-foco': 'novo-assunto' }, 'primario')),
    estado.mensagem,
    estado.lista);
  estado.lista.replaceChildren(estadoCarregando());
  await carregar();
}

async function carregar(foco) {
  const resposta = await api(`/assuntos?situacao=${estado.mostrarExcluidos ? 'todos' : 'ativos'}&tipo=${estado.tipo}`);
  if (!resposta.ok) {
    estado.lista.replaceChildren(estadoErro(resposta.dados.mensagem || SEM_CONEXAO, () => {
      estado.lista.replaceChildren(estadoCarregando());
      carregar(foco);
    }));
    return;
  }
  estado.assuntos = resposta.dados.itens;
  renderizar();
  focarDepois(foco);
}

function renderizar() {
  const faixas = estado.assuntos.map(faixaAssunto);
  if (estado.editor?.tipo === 'assunto-novo') faixas.push(formAssunto(null));
  if (!faixas.length) {
    estado.lista.replaceChildren(estadoVazio('Nenhum assunto cadastrado ainda.', 'Criar o primeiro assunto', novoAssunto));
    return;
  }
  estado.lista.replaceChildren(...faixas);
  if (estado.falha) {
    estado.falha();
    estado.falha = null;
  }
}

async function abrirEditor(editor) {
  if (!(await editores.liberar())) return false;
  estado.editor = editor;
  renderizar();
  return true;
}

function fecharEditor() {
  estado.editor = null;
  renderizar();
}

async function novoAssunto() {
  if (await abrirEditor({ tipo: 'assunto-novo' })) focarDepois('assunto-novo:nome');
}

function faixaAssunto(assunto) {
  const excluido = Boolean(assunto.excluido_em);
  const aberto = estado.abertos.has(assunto.id);
  const corpoId = `corpo_assunto_${assunto.id}`;
  const renomeando = estado.editor?.tipo === 'renomear' && estado.editor.id === assunto.id;

  const corpo = el('div', { class: 'flori-ct-faixa-corpo', id: corpoId, hidden: !aberto }, corpoAssunto(assunto));
  const alternar = el('button', {
    type: 'button', class: 'flori-ct-alternar', 'aria-expanded': String(aberto), 'aria-controls': corpoId,
    'data-foco': `assunto:${assunto.id}`,
  },
  icone(ICONES.seta),
  el('span', { class: 'flori-ct-nome', text: assunto.titulo }),
  el('span', { class: 'flori-ct-meta', text: plural(assunto.total_cards, 'card', 'cards') }),
  chipSituacao(assunto));
  alternar.addEventListener('click', () => {
    const abrir = alternar.getAttribute('aria-expanded') !== 'true';
    alternar.setAttribute('aria-expanded', String(abrir));
    corpo.hidden = !abrir;
    if (abrir) estado.abertos.add(assunto.id);
    else estado.abertos.delete(assunto.id);
  });

  const acoes = excluido
    ? [botao('Restaurar', { onclick: () => restaurar('assuntos', assunto.id, 'Assunto restaurado'), 'data-foco': `assunto:${assunto.id}:restaurar` })]
    : [
      botao('Renomear', { onclick: () => abrirEditor({ tipo: 'renomear', id: assunto.id }).then((ok) => ok && focarDepois(`renomear:${assunto.id}`)) }),
      botao(assunto.ativo ? 'Desativar' : 'Ativar', {
        'data-foco': `assunto:${assunto.id}:situacao`,
        onclick: () => alternarSituacao('assuntos', assunto, 'Assunto', `assunto:${assunto.id}:situacao`),
      }),
      botao('Excluir', { onclick: () => excluirAssunto(assunto) }, 'perigo'),
    ];

  const topo = renomeando
    ? formAssunto(assunto)
    : el('div', { class: 'flori-ct-faixa-topo' }, alternar, el('div', { class: 'flori-ct-acoes' }, acoes));
  return el('section', { class: `flori-ct-faixa${excluido ? ' is-excluido' : ''}`, 'aria-label': assunto.titulo }, topo, corpo);
}

function corpoAssunto(assunto) {
  const excluido = Boolean(assunto.excluido_em);
  const ativos = assunto.cards.filter((c) => !c.excluido_em);
  const itens = [];
  assunto.cards.forEach((card) => {
    itens.push(linhaCard(card, assunto, ativos.indexOf(card), ativos.length));
    if (estado.editor?.tipo === 'card' && estado.editor.id === card.id) itens.push(editorCard(card, assunto));
  });
  const criando = estado.editor?.tipo === 'card' && estado.editor.id === null && estado.editor.assuntoId === assunto.id;
  if (criando) itens.push(editorCard({ titulo: '', explicacao: '', exemplo: '', fontes: [{ nome: '', url: '' }] }, assunto));
  if (!assunto.cards.length && !criando) {
    if (excluido) return el('p', { class: 'flori-hint', text: 'Nenhum card neste assunto.' });
    return estadoVazio('Nenhum card neste assunto ainda.', 'Criar o primeiro card', () => novoCard(assunto));
  }
  if (!excluido && !criando) {
    itens.push(botao(`+ Novo card em ${assunto.titulo}`, {
      class: 'btn btn-flori btn-flori-sm flori-ct-novo', onclick: () => novoCard(assunto),
    }));
  }
  return itens;
}

async function novoCard(assunto) {
  estado.abertos.add(assunto.id);
  if (await abrirEditor({ tipo: 'card', id: null, assuntoId: assunto.id })) focarDepois('editor-card:titulo');
}

function linhaCard(card, assunto, posicao, total) {
  const excluido = Boolean(card.excluido_em);
  const editando = estado.editor?.tipo === 'card' && estado.editor.id === card.id;
  const chave = `card:${card.id}`;
  const acoes = excluido
    ? [botao('Restaurar', { 'data-foco': `${chave}:restaurar`, onclick: () => restaurar('cards', card.id, 'Card restaurado') })]
    : [
      setas({
        nome: 'card', numero: posicao + 1, posicao, total, chave,
        aoMover: (direcao) => mover('cards', card.id, direcao, chave),
      }),
      botao(editando ? 'Fechar' : 'Editar', {
        'data-foco': `${chave}:editar`, 'aria-expanded': String(editando),
        onclick: () => (editando ? editores.liberar() : abrirEditor({ tipo: 'card', id: card.id })
          .then((ok) => ok && focarDepois('editor-card:titulo'))),
      }),
      botao(card.ativo ? 'Desativar' : 'Ativar', {
        'data-foco': `${chave}:situacao`, onclick: () => alternarSituacao('cards', card, 'Card', `${chave}:situacao`),
      }),
      botao('Excluir', { onclick: () => excluirCard(card) }, 'perigo'),
    ];
  return el('div', { class: `flori-ct-linha${excluido ? ' is-excluido' : ''}${editando ? ' is-aberto' : ''}` },
    el('span', { class: 'flori-ct-numero', 'aria-hidden': 'true', text: excluido ? '·' : String(posicao + 1) }),
    el('div', { class: 'flori-ct-linha-texto' },
      el('span', { class: 'flori-ct-linha-titulo', text: card.titulo }),
      el('span', { class: 'flori-ct-meta', text: plural(card.total_fontes, 'fonte', 'fontes') })),
    chipSituacao(card),
    el('div', { class: 'flori-ct-acoes' }, acoes));
}

function formAssunto(assunto) {
  const novo = !assunto;
  const original = novo ? '' : assunto.titulo;
  const chave = novo ? 'assunto-novo' : `renomear:${assunto.id}`;
  const campo = campoTexto({
    id: novo ? 'novoAssuntoNome' : `renomear_${assunto.id}`, rotulo: 'Nome do assunto', valor: original,
    maximo: LIMITES.assunto, aoMudar: () => { salvar.disabled = !campo.entrada.value.trim(); },
  });
  campo.entrada.dataset.foco = novo ? 'assunto-novo:nome' : chave;
  const resumo = caixaResumo();
  const editor = {
    sujo: () => campo.entrada.value.trim() !== original,
    fechar: fecharEditor,
  };
  editores.abrir(editor);
  const salvar = botaoSalvar(novo ? 'Salvar assunto' : 'Salvar nome', async () => {
    limparErros(resumo, { titulo: campo });
    const corpo = novo
      ? { titulo: campo.entrada.value, tipo: estado.tipo }
      : { titulo: campo.entrada.value, atualizado_em: assunto.atualizado_em };
    const resposta = await api(novo ? '/assuntos' : `/assuntos/${assunto.id}`, { metodo: novo ? 'POST' : 'PUT', corpo });
    if (!resposta.ok) {
      mostrarFalha(resposta, { resumo, campos: { titulo: campo }, aoRecarregar: () => { editores.soltar(editor); estado.editor = null; carregar(); } });
      return;
    }
    editores.soltar(editor);
    estado.editor = null;
    toast('Assunto salvo');
    await carregar(`assunto:${resposta.dados.id}`);
  }, () => Boolean(campo.entrada.value.trim()));
  return el('div', { class: `flori-ct-form-inline${novo ? ' flori-ct-faixa' : ''}` },
    resumo, campo.bloco,
    el('div', { class: 'flori-ct-rodape' },
      el('span'),
      el('div', { class: 'flori-ct-acoes' }, botao('Cancelar', { onclick: () => editores.liberar() }), salvar)));
}

function editorCard(card, assunto) {
  const novo = !card.id;
  const fontes = card.fontes.map((f) => ({ ...f }));
  if (!fontes.length) fontes.push({ nome: '', url: '' });
  const campos = {};
  const resumo = caixaResumo();
  campos.titulo = campoTexto({ id: 'edCardTitulo', rotulo: 'Título do card', valor: card.titulo, maximo: LIMITES.titulo });
  campos.titulo.entrada.dataset.foco = 'editor-card:titulo';
  campos.explicacao = campoTexto({
    id: 'edCardExplicacao', rotulo: 'Explicação', valor: card.explicacao, maximo: LIMITES.explicacao, area: true, linhas: 5,
  });
  campos.exemplo = campoTexto({
    id: 'edCardExemplo', rotulo: 'Exemplo', valor: card.exemplo, maximo: LIMITES.exemplo, area: true, linhas: 2,
  });

  const listaFontes = el('div', { class: 'flori-ct-fontes' });
  const erroFontes = el('small', { class: 'flori-ct-erro-campo', id: 'edCardFontes_erro', hidden: true });
  const adicionar = botao('+ Adicionar fonte', { id: 'edCardFontes' }, 'link');
  campos.fontes = { entrada: adicionar, erro: erroFontes };

  const ler = () => ({
    titulo: campos.titulo.entrada.value,
    explicacao: campos.explicacao.entrada.value,
    exemplo: campos.exemplo.entrada.value,
    fontes: fontes.map((f) => ({ nome: f.nome, url: f.url })),
  });
  const original = JSON.stringify(ler());

  function desenharFontes(focarIndice) {
    Object.keys(campos).filter((k) => k.startsWith('fontes.')).forEach((k) => delete campos[k]);
    listaFontes.replaceChildren(...fontes.map((fonte, i) => {
      const nome = campoTexto({
        id: `edFonteNome${i}`, rotulo: 'Nome', valor: fonte.nome, maximo: LIMITES.fonteNome,
        aoMudar: () => { fonte.nome = nome.entrada.value; },
      });
      const url = campoTexto({
        id: `edFonteUrl${i}`, rotulo: 'Link', valor: fonte.url, maximo: LIMITES.fonteUrl,
        aoMudar: () => { fonte.url = url.entrada.value; },
      });
      url.entrada.type = 'url';
      url.entrada.placeholder = 'https://';
      nome.entrada.dataset.foco = `fonte:${i}`;
      campos[`fontes.${i}.nome`] = nome;
      campos[`fontes.${i}.url`] = url;
      return el('div', { class: 'flori-ct-fonte', role: 'group', 'aria-label': `Fonte ${i + 1}` },
        nome.bloco, url.bloco,
        botao('Remover', {
          'aria-label': `Remover fonte ${i + 1}`,
          onclick: () => {
            fontes.splice(i, 1);
            desenharFontes();
            adicionar.focus();
          },
        }, 'perigo'));
    }));
    if (focarIndice !== undefined) focarDepois(`fonte:${focarIndice}`);
  }
  adicionar.addEventListener('click', () => {
    fontes.push({ nome: '', url: '' });
    desenharFontes(fontes.length - 1);
  });
  desenharFontes();

  const editor = { sujo: () => JSON.stringify(ler()) !== original, fechar: fecharEditor };
  editores.abrir(editor);

  const recarregar = async () => {
    editores.soltar(editor);
    await carregar('editor-card:titulo');
  };
  const salvar = botaoSalvar('Salvar card', async () => {
    limparErros(resumo, campos);
    const corpo = novo ? { ...ler(), assunto_id: assunto.id } : { ...ler(), atualizado_em: card.atualizado_em };
    const resposta = await api(novo ? '/cards' : `/cards/${card.id}`, { metodo: novo ? 'POST' : 'PUT', corpo });
    if (!resposta.ok) {
      mostrarFalha(resposta, { resumo, campos, aoRecarregar: recarregar });
      return;
    }
    editores.soltar(editor);
    estado.editor = null;
    toast('Card salvo');
    await carregar(`card:${resposta.dados.id}:editar`);
  });

  const visualizar = botao('Visualizar', {
    onclick: async () => {
      const dados = ler();
      previaCard({
        tema: dados.titulo, explicacao: dados.explicacao, exemplo: dados.exemplo, secoes: card.secoes || [], cta: '',
        fontes: dados.fontes.filter((f) => /^https?:\/\//i.test(f.url.trim())), concluido: false,
        aviso: assunto.aviso || '',
      }, { titulo: assunto.titulo, cor: assunto.cor });
    },
  });

  const bloco = el('div', { class: 'flori-ct-editor', role: 'group', 'aria-label': novo ? 'Novo card' : `Editar card ${card.titulo}` },
    resumo,
    campos.titulo.bloco, campos.explicacao.bloco, campos.exemplo.bloco,
    el('fieldset', { class: 'flori-ct-campo' },
      el('legend', { class: 'form-label', text: 'Fontes' }),
      listaFontes, adicionar, erroFontes),
    el('div', { class: 'flori-ct-rodape' },
      visualizar,
      el('div', { class: 'flori-ct-acoes' }, botao('Cancelar', { onclick: () => editores.liberar() }), salvar)));
  editor.mostrarFalha = (resposta) => mostrarFalha(resposta, { resumo, campos, aoRecarregar: recarregar });
  return bloco;
}

async function alternarSituacao(recurso, item, rotulo, foco) {
  const ativar = !item.ativo;
  const resposta = await executarAcao({
    caminho: `/${recurso}/${item.id}/${ativar ? 'ativar' : 'desativar'}`,
    caixa: estado.mensagem,
    sucesso: `${rotulo} ${ativar ? 'ativado' : 'desativado'}`,
    depois: () => carregar(foco),
  });
  if (resposta && !resposta.ok && resposta.dados.campos && recurso === 'cards') {
    mostrarMensagem(estado.mensagem, '');
    estado.editor = { tipo: 'card', id: item.id };
    estado.falha = () => editores.atual()?.mostrarFalha?.(resposta);
    estado.abertos.add(item.assunto_id);
    renderizar();
  }
}

async function mover(recurso, id, direcao, chave) {
  await executarAcao({
    caminho: `/${recurso}/${id}/reordenar`, corpo: { direcao }, caixa: estado.mensagem,
    depois: () => carregar(`${chave}:${direcao}`),
  });
}

async function restaurar(recurso, id, sucesso) {
  await executarAcao({
    caminho: `/${recurso}/${id}/restaurar`, caixa: estado.mensagem, sucesso,
    depois: () => carregar(),
  });
}

async function impacto(recurso, id) {
  const resposta = await api(`/${recurso}/${id}/impacto`);
  if (!resposta.ok) {
    mostrarMensagem(estado.mensagem, resposta.dados.mensagem || SEM_CONEXAO);
    return null;
  }
  return resposta.dados;
}

async function excluirCard(card) {
  if (!(await editores.liberar())) return;
  const dados = await impacto('cards', card.id);
  if (!dados) return;
  let texto = 'Ele sai da trilha e deixa de aparecer para os users.';
  if (dados.pessoas_concluiram === 1) texto += ' 1 pessoa já concluiu este card.';
  else if (dados.pessoas_concluiram > 1) texto += ` ${dados.pessoas_concluiram} pessoas já concluíram este card.`;
  const sim = await confirmar({
    titulo: `Excluir o card "${card.titulo}"?`,
    texto,
    itens: [
      'Quem já concluiu a trilha continua concluída, com o certificado.',
      'Quem estava no meio recebe o andamento recalculado sem esse card.',
      'O card fica guardado e pode ser restaurado em "Mostrar excluídos".',
    ],
  });
  if (!sim) return;
  await executarAcao({
    caminho: `/cards/${card.id}/excluir`, caixa: estado.mensagem, sucesso: 'Card excluído', depois: () => carregar(),
  });
}

async function excluirAssunto(assunto) {
  if (!(await editores.liberar())) return;
  const dados = await impacto('assuntos', assunto.id);
  if (!dados) return;
  let texto = `Os ${dados.cards} cards deste assunto também saem da trilha.`;
  if (dados.cards === 1) texto = 'O único card deste assunto também sai da trilha.';
  if (dados.cards === 0) texto = 'Este assunto ainda não tem cards.';
  const sim = await confirmar({
    titulo: `Excluir o assunto "${assunto.titulo}"?`,
    texto,
    itens: [
      'O progresso e os certificados já registrados são mantidos.',
      'Tudo fica guardado e pode ser restaurado em "Mostrar excluídos".',
    ],
  });
  if (!sim) return;
  await executarAcao({
    caminho: `/assuntos/${assunto.id}/excluir`, caixa: estado.mensagem, sucesso: 'Assunto excluído',
    depois: () => carregar(),
  });
}
