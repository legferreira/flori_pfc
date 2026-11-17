import {
  SEM_CONEXAO, api, botaoSalvar, caixaExcluidos, caixaMensagem, caixaResumo, chipSituacao, editores, executarAcao,
  limparErros, mostrarFalha, mostrarMensagem, plural, previaGuia, setas,
} from './conteudo-comum.js';
import {
  ICONES, botao, campoTexto, confirmar, el, estadoCarregando, estadoErro, estadoVazio, focarDepois, icone, toast,
} from './interface.js';

const LIMITES = { titulo: 80, passo: 200, passos: 8 };

const estado = { guias: [], mostrarExcluidos: false, editor: undefined, lista: null, mensagem: null, falha: null };

export async function desenharGuias(raiz) {
  estado.editor = undefined;
  estado.lista = el('div', { class: 'flori-ct-lista' });
  estado.mensagem = caixaMensagem();
  raiz.replaceChildren(
    el('p', {
      class: 'flori-ct-aviso',
      text: 'Cards fora da trilha, exibidos acima dela. Todos os guias ativos aparecem para os users, na ordem abaixo.',
    }),
    el('div', { class: 'flori-ct-barra' },
      caixaExcluidos('Mostrar excluídos', estado.mostrarExcluidos, (marcado) => {
        estado.mostrarExcluidos = marcado;
        carregar();
      }),
      botao('Novo guia', { onclick: novoGuia, 'data-foco': 'novo-guia' }, 'primario')),
    estado.mensagem,
    estado.lista);
  estado.lista.replaceChildren(estadoCarregando());
  await carregar();
}

async function carregar(foco) {
  const resposta = await api(`/guias?situacao=${estado.mostrarExcluidos ? 'todos' : 'ativos'}`);
  if (!resposta.ok) {
    estado.lista.replaceChildren(estadoErro(resposta.dados.mensagem || SEM_CONEXAO, () => {
      estado.lista.replaceChildren(estadoCarregando());
      carregar(foco);
    }));
    return;
  }
  estado.guias = resposta.dados.itens;
  renderizar();
  focarDepois(foco);
}

function renderizar() {
  const ativos = estado.guias.filter((g) => !g.excluido_em);
  const faixas = estado.guias.map((g) => faixaGuia(g, ativos.indexOf(g), ativos.length));
  if (estado.editor === null) faixas.push(faixaGuia(null, -1, ativos.length));
  if (!faixas.length) {
    estado.lista.replaceChildren(estadoVazio('Nenhum guia cadastrado ainda.', 'Criar o primeiro guia', novoGuia));
    return;
  }
  estado.lista.replaceChildren(...faixas);
  if (estado.falha) {
    estado.falha();
    estado.falha = null;
  }
}

async function abrirEditor(id) {
  if (!(await editores.liberar())) return false;
  estado.editor = id;
  renderizar();
  return true;
}

function fecharEditor() {
  estado.editor = undefined;
  renderizar();
}

async function novoGuia() {
  if (await abrirEditor(null)) focarDepois('editor-guia:titulo');
}

function faixaGuia(guia, posicao, total) {
  const novo = !guia;
  const dados = guia || { id: null, titulo: '', passos: [''], ativo: true, excluido_em: null, total_passos: 0 };
  const excluido = Boolean(dados.excluido_em);
  const aberto = estado.editor === dados.id;
  const chave = `guia:${dados.id || 'novo'}`;
  const corpoId = `corpo_${chave.replace(':', '_')}`;

  const alternar = el('button', {
    type: 'button', class: 'flori-ct-alternar', 'aria-expanded': String(aberto), 'aria-controls': corpoId,
    'data-foco': chave, disabled: excluido,
  },
  icone(ICONES.seta),
  el('span', { class: 'flori-ct-nome', text: novo ? 'Novo guia' : dados.titulo }),
  novo ? null : el('span', { class: 'flori-ct-meta', text: plural(dados.total_passos, 'passo', 'passos') }),
  novo ? null : chipSituacao(dados));
  alternar.addEventListener('click', async () => {
    if (aberto) await editores.liberar();
    else if (await abrirEditor(dados.id)) focarDepois('editor-guia:titulo');
  });

  const acoes = [];
  if (excluido) {
    acoes.push(botao('Restaurar', { 'data-foco': `${chave}:restaurar`, onclick: () => restaurar(dados.id) }));
  } else if (!novo) {
    acoes.push(
      setas({ nome: 'guia', numero: posicao + 1, posicao, total, chave, aoMover: (direcao) => mover(dados.id, direcao) }),
      botao(dados.ativo ? 'Desativar' : 'Ativar', { 'data-foco': `${chave}:situacao`, onclick: () => alternarSituacao(dados) }),
      botao('Excluir', { onclick: () => excluir(dados) }, 'perigo'),
    );
  }

  return el('section', {
    class: `flori-ct-faixa${excluido ? ' is-excluido' : ''}${aberto ? ' is-aberto' : ''}`,
    'aria-label': novo ? 'Novo guia' : dados.titulo,
  },
  el('div', { class: 'flori-ct-faixa-topo' }, alternar, el('div', { class: 'flori-ct-acoes' }, acoes)),
  aberto ? el('div', { class: 'flori-ct-faixa-corpo', id: corpoId }, editorGuia(dados)) : null);
}

function editorGuia(guia) {
  const novo = !guia.id;
  const passos = (guia.passos.length ? guia.passos : ['']).map((texto) => ({ texto }));
  const campos = {};
  const resumo = caixaResumo();
  campos.titulo = campoTexto({ id: 'edGuiaTitulo', rotulo: 'Título', valor: guia.titulo, maximo: LIMITES.titulo });
  campos.titulo.entrada.dataset.foco = 'editor-guia:titulo';

  const listaPassos = el('ol', { class: 'flori-ct-passos' });
  const erroPassos = el('small', { class: 'flori-ct-erro-campo', id: 'edGuiaPassos_erro', hidden: true });
  const adicionar = botao('+ Adicionar passo', { id: 'edGuiaPassos' }, 'link');
  campos.passos = { entrada: adicionar, erro: erroPassos };

  const ler = () => ({ titulo: campos.titulo.entrada.value, passos: passos.map((p) => p.texto) });
  const original = JSON.stringify(ler());

  function desenharPassos(foco) {
    Object.keys(campos).filter((k) => k.startsWith('passos.')).forEach((k) => delete campos[k]);
    listaPassos.replaceChildren(...passos.map((passo, i) => {
      const campo = campoTexto({
        id: `edPasso${i}`, valor: passo.texto, maximo: LIMITES.passo,
        aoMudar: () => { passo.texto = campo.entrada.value; },
      });
      campo.entrada.setAttribute('aria-label', `Passo ${i + 1}`);
      campo.entrada.dataset.foco = `passo:${i}`;
      campos[`passos.${i}`] = campo;
      const trocar = (destino) => {
        [passos[i], passos[destino]] = [passos[destino], passos[i]];
        desenharPassos(`passo:${destino}`);
      };
      return el('li', { class: 'flori-ct-passo' },
        el('span', { class: 'flori-ct-numero', 'aria-hidden': 'true', text: String(i + 1) }),
        campo.bloco,
        setas({
          nome: 'passo', numero: i + 1, posicao: i, total: passos.length, chave: `passo:${i}`,
          aoMover: (direcao) => trocar(direcao === 'subir' ? i - 1 : i + 1),
        }),
        botao('Remover', {
          'aria-label': `Remover passo ${i + 1}`, disabled: passos.length === 1,
          onclick: () => {
            passos.splice(i, 1);
            desenharPassos();
            adicionar.focus();
          },
        }, 'perigo'));
    }));
    adicionar.disabled = passos.length >= LIMITES.passos;
    focarDepois(foco);
  }
  adicionar.addEventListener('click', () => {
    passos.push({ texto: '' });
    desenharPassos(`passo:${passos.length - 1}`);
  });
  desenharPassos();

  const editor = { sujo: () => JSON.stringify(ler()) !== original, fechar: fecharEditor };
  editores.abrir(editor);
  const recarregar = async () => {
    editores.soltar(editor);
    await carregar('editor-guia:titulo');
  };
  const salvar = botaoSalvar('Salvar guia', async () => {
    limparErros(resumo, campos);
    const corpo = novo ? ler() : { ...ler(), atualizado_em: guia.atualizado_em };
    const resposta = await api(novo ? '/guias' : `/guias/${guia.id}`, { metodo: novo ? 'POST' : 'PUT', corpo });
    if (!resposta.ok) {
      mostrarFalha(resposta, { resumo, campos, aoRecarregar: recarregar });
      return;
    }
    editores.soltar(editor);
    estado.editor = undefined;
    toast('Guia salvo');
    await carregar(`guia:${resposta.dados.id}`);
  });

  editor.mostrarFalha = (resposta) => mostrarFalha(resposta, { resumo, campos, aoRecarregar: recarregar });
  return el('div', { class: 'flori-ct-editor', role: 'group', 'aria-label': novo ? 'Novo guia' : `Editar guia ${guia.titulo}` },
    resumo,
    campos.titulo.bloco,
    el('fieldset', { class: 'flori-ct-campo' },
      el('legend', { class: 'form-label', text: 'Passos' }),
      listaPassos, adicionar, erroPassos),
    el('div', { class: 'flori-ct-rodape' },
      botao('Visualizar', {
        onclick: () => previaGuia({ titulo: campos.titulo.entrada.value, introducao: '', passos: ler().passos, fontes: [] }),
      }),
      el('div', { class: 'flori-ct-acoes' }, botao('Cancelar', { onclick: () => editores.liberar() }), salvar)));
}

async function alternarSituacao(guia) {
  const ativar = !guia.ativo;
  const resposta = await executarAcao({
    caminho: `/guias/${guia.id}/${ativar ? 'ativar' : 'desativar'}`,
    caixa: estado.mensagem,
    sucesso: `Guia ${ativar ? 'ativado' : 'desativado'}`,
    depois: () => carregar(`guia:${guia.id}:situacao`),
  });
  if (resposta && !resposta.ok && resposta.dados.campos) {
    mostrarMensagem(estado.mensagem, '');
    estado.editor = guia.id;
    estado.falha = () => editores.atual()?.mostrarFalha?.(resposta);
    renderizar();
  }
}

async function mover(id, direcao) {
  await executarAcao({
    caminho: `/guias/${id}/reordenar`, corpo: { direcao }, caixa: estado.mensagem,
    depois: () => carregar(`guia:${id}:${direcao}`),
  });
}

async function restaurar(id) {
  await executarAcao({
    caminho: `/guias/${id}/restaurar`, caixa: estado.mensagem, sucesso: 'Guia restaurado', depois: () => carregar(),
  });
}

async function excluir(guia) {
  if (!(await editores.liberar())) return;
  const resposta = await api(`/guias/${guia.id}/impacto`);
  if (!resposta.ok) {
    mostrarMensagem(estado.mensagem, resposta.dados.mensagem || SEM_CONEXAO);
    return;
  }
  const n = resposta.dados.passos;
  const texto = n === 1
    ? 'O guia e seu único passo deixam de aparecer para os users.'
    : `O guia e seus ${n} passos deixam de aparecer para os users.`;
  const sim = await confirmar({
    titulo: `Excluir o guia "${guia.titulo}"?`,
    texto,
    itens: ['O guia fica guardado e pode ser restaurado em "Mostrar excluídos".'],
  });
  if (!sim) return;
  await executarAcao({
    caminho: `/guias/${guia.id}/excluir`, caixa: estado.mensagem, sucesso: 'Guia excluído', depois: () => carregar(),
  });
}
