import {
  SEM_CONEXAO, api, botaoSalvar, caixaExcluidos, caixaMensagem, caixaResumo, chipSituacao, editores, executarAcao,
  limparErros, mostrarFalha, mostrarMensagem, plural, previaPergunta, setas,
} from './conteudo-comum.js';
import {
  ICONES, botao, campoTexto, confirmar, el, estadoCarregando, estadoErro, estadoVazio, focarDepois, icone,
  mostrarErroCampo, toast,
} from './interface.js';

const LIMITES = { enunciado: 200, opcao: 120 };
const LETRAS = ['A', 'B', 'C', 'D'];
const IDEAL = 10;

const estado = {
  perguntas: [], resumo: null, mostrarExcluidas: false, editor: undefined, lista: null, topo: null, mensagem: null,
  falha: null,
};

export async function desenharQuiz(raiz) {
  estado.editor = undefined;
  estado.lista = el('div', { class: 'flori-ct-lista' });
  estado.topo = el('div', { class: 'flori-ct-quiz-topo' });
  estado.mensagem = caixaMensagem();
  raiz.replaceChildren(estado.topo, estado.mensagem, estado.lista);
  estado.lista.replaceChildren(estadoCarregando());
  await carregar();
}

async function carregar(foco) {
  const [lista, resumo] = await Promise.all([
    api(`/perguntas?situacao=${estado.mostrarExcluidas ? 'todos' : 'ativos'}`),
    api('/quiz/resumo'),
  ]);
  if (!lista.ok || !resumo.ok) {
    const falha = !lista.ok ? lista : resumo;
    estado.lista.replaceChildren(estadoErro(falha.dados.mensagem || SEM_CONEXAO, () => {
      estado.lista.replaceChildren(estadoCarregando());
      carregar(foco);
    }));
    return;
  }
  estado.perguntas = lista.dados.itens;
  estado.resumo = resumo.dados;
  renderizar();
  focarDepois(foco);
}

function textoResumo(ativas) {
  if (ativas >= IDEAL) {
    return 'Cada tentativa mostra 10 perguntas, sorteadas entre as ativas. Aprovação com 70% de acertos. '
      + 'Mudar, desativar ou excluir uma pergunta não altera tentativas e certificados que já existem.';
  }
  if (ativas > 0) {
    return 'Cada tentativa mostra até 10 perguntas, sorteadas entre as ativas. Com menos de 10 ativas o quiz continua '
      + `funcionando e a nota é calculada sobre as perguntas da tentativa (hoje, ${ativas}). O ideal é manter 10 ou mais. `
      + 'Aprovação com 70% de acertos. Mudar, desativar ou excluir uma pergunta não altera tentativas e certificados que já existem.';
  }
  return 'Sem perguntas ativas, o quiz fica indisponível para os users.';
}

function renderizarTopo() {
  const { cadastradas, ativas } = estado.resumo;
  let tipo = 'is-zero';
  if (ativas >= IDEAL) tipo = 'is-ok';
  else if (ativas > 0) tipo = 'is-alerta';
  estado.topo.replaceChildren(
    el('div', { class: 'flori-ct-barra' },
      el('div', { class: `flori-ct-contador-quiz ${tipo}`, role: 'status' },
        icone(ativas >= IDEAL ? ICONES.certo : ICONES.alerta),
        el('span', { text: `${plural(cadastradas, 'pergunta cadastrada', 'perguntas cadastradas')} · ${plural(ativas, 'ativa', 'ativas')}` })),
      el('div', { class: 'flori-ct-acoes' },
        caixaExcluidos('Mostrar excluídas', estado.mostrarExcluidas, (marcado) => {
          estado.mostrarExcluidas = marcado;
          carregar();
        }),
        botao('Nova pergunta do quiz', { onclick: novaPergunta, 'data-foco': 'nova-pergunta' }, 'primario'))),
    el('p', { class: 'flori-ct-aviso', text: textoResumo(ativas) }));
}

function renderizar() {
  renderizarTopo();
  const ativas = estado.perguntas.filter((p) => !p.excluido_em);
  const blocos = estado.perguntas.map((p) => blocoPergunta(p, ativas.indexOf(p), ativas.length));
  if (estado.editor === null) blocos.push(blocoPergunta(null, -1, ativas.length));
  if (!blocos.length) {
    estado.lista.replaceChildren(estadoVazio('Nenhuma pergunta cadastrada ainda.', 'Criar a primeira pergunta', novaPergunta));
    return;
  }
  estado.lista.replaceChildren(...blocos);
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

async function novaPergunta() {
  if (await abrirEditor(null)) focarDepois('editor-pergunta:enunciado');
}

function blocoPergunta(pergunta, posicao, total) {
  const nova = !pergunta;
  const dados = pergunta || {
    id: null, enunciado: '', ativo: true, excluido_em: null,
    opcoes: LETRAS.map(() => ({ id: null, texto: '', correta: false })),
  };
  const excluida = Boolean(dados.excluido_em);
  const aberta = estado.editor === dados.id;
  const chave = `pergunta:${dados.id || 'nova'}`;
  const numero = excluida || nova ? '·' : String(posicao + 1);

  const resumoLinha = dados.correta
    ? `${plural(dados.opcoes.length, 'opção', 'opções')} · correta: ${dados.correta}`
    : plural(dados.opcoes.length, 'opção', 'opções');

  const acoes = [];
  if (excluida) {
    acoes.push(botao('Restaurar', { 'data-foco': `${chave}:restaurar`, onclick: () => restaurar(dados.id) }));
  } else if (!nova) {
    acoes.push(
      botao(aberta ? 'Fechar' : 'Editar', {
        'data-foco': `${chave}:editar`, 'aria-expanded': String(aberta),
        onclick: () => (aberta ? editores.liberar() : abrirEditor(dados.id).then((ok) => ok && focarDepois('editor-pergunta:enunciado'))),
      }),
      botao(dados.ativo ? 'Desativar' : 'Ativar', { 'data-foco': `${chave}:situacao`, onclick: () => alternarSituacao(dados) }),
      botao('Excluir', { onclick: () => excluir(dados) }, 'perigo'),
    );
  }

  const topo = el('div', { class: 'flori-ct-bloco-topo' },
    el('span', { class: 'flori-ct-numero', 'aria-hidden': 'true', text: numero }),
    el('div', { class: 'flori-ct-linha-texto' },
      el('span', { class: 'flori-ct-linha-titulo', text: nova ? 'Nova pergunta do quiz' : dados.enunciado }),
      nova ? null : el('span', { class: 'flori-ct-meta', text: resumoLinha })),
    nova ? null : chipSituacao(dados, true),
    el('div', { class: 'flori-ct-acoes' }, acoes));

  return el('article', {
    class: `flori-ct-bloco${aberta ? ' is-aberto' : ''}${excluida ? ' is-excluido' : ''}`,
    'aria-label': nova ? 'Nova pergunta do quiz' : `Pergunta ${numero}`,
  }, topo, aberta ? editorPergunta(dados, posicao, total) : null);
}

function normalizar(texto) {
  return texto.replace(/\s+/g, ' ').trim().toLowerCase();
}

function editorPergunta(pergunta, posicao, total) {
  const nova = !pergunta.id;
  const opcoes = pergunta.opcoes.slice(0, 4).map((o) => ({ ...o }));
  while (opcoes.length < 4) opcoes.push({ id: null, texto: '', correta: false });
  const campos = {};
  const resumo = caixaResumo();
  const nomeRadio = `correta_${pergunta.id || 'nova'}`;

  campos.enunciado = campoTexto({
    id: 'edPerguntaEnunciado', rotulo: 'Enunciado', valor: pergunta.enunciado, maximo: LIMITES.enunciado,
    aoMudar: atualizar,
  });
  campos.enunciado.entrada.dataset.foco = 'editor-pergunta:enunciado';

  const linhas = opcoes.map((opcao, i) => {
    const entrada = el('input', {
      type: 'text', class: 'flori-ct-opcao-texto', id: `edOpcao${i}`, maxlength: LIMITES.opcao,
      'aria-label': `Texto da opção ${LETRAS[i]}`, value: opcao.texto,
    });
    const radio = el('input', {
      type: 'radio', name: nomeRadio, class: 'form-check-input', id: `edCorreta${i}`, checked: opcao.correta,
      'aria-label': `Marcar a opção ${LETRAS[i]} como correta`,
    });
    const erro = el('small', { class: 'flori-ct-erro-campo', id: `edOpcao${i}_erro`, hidden: true });
    const contador = el('small', { class: 'flori-ct-contador', id: `edOpcao${i}_contador` });
    entrada.setAttribute('aria-describedby', contador.id);
    const tag = el('span', { class: 'flori-ct-tag-correta', text: 'Correta', hidden: !opcao.correta });
    const linha = el('div', { class: `flori-ct-opcao${opcao.correta ? ' is-correta' : ''}` },
      radio, el('span', { class: 'flori-ct-letra', 'aria-hidden': 'true', text: LETRAS[i] }), entrada, tag);
    entrada.addEventListener('input', () => { opcao.texto = entrada.value; atualizar(); });
    radio.addEventListener('change', () => {
      opcoes.forEach((o, k) => { o.correta = k === i; });
      atualizar();
    });
    campos[`opcoes.${i}.texto`] = { entrada, erro };
    return { linha, entrada, radio, tag, erro, contador, bloco: el('div', {}, linha, el('div', { class: 'flori-ct-campo-pe' }, erro, contador)) };
  });
  const erroOpcoes = el('small', { class: 'flori-ct-erro-campo', id: 'edOpcoes_erro', hidden: true });
  campos.opcoes = { entrada: linhas[0].radio, erro: erroOpcoes };

  const ler = () => ({
    enunciado: campos.enunciado.entrada.value,
    opcoes: opcoes.map((o) => ({ ...(o.id ? { id: o.id } : {}), texto: o.texto, correta: o.correta })),
  });
  const original = JSON.stringify(ler());

  function valida() {
    const enunciado = campos.enunciado.entrada.value.trim();
    if (!enunciado || enunciado.length > LIMITES.enunciado) return false;
    const textos = opcoes.map((o) => normalizar(o.texto));
    if (textos.some((t) => !t)) return false;
    if (new Set(textos).size !== textos.length) return false;
    return opcoes.filter((o) => o.correta).length === 1;
  }

  let salvar = null;
  function atualizar() {
    linhas.forEach((l, i) => {
      l.contador.textContent = `${opcoes[i].texto.length} de ${LIMITES.opcao}`;
      l.tag.hidden = !opcoes[i].correta;
      l.linha.classList.toggle('is-correta', opcoes[i].correta);
    });
    const textos = opcoes.map((o) => normalizar(o.texto));
    linhas.forEach((l, i) => {
      const repetida = textos[i] && textos.indexOf(textos[i]) !== i;
      mostrarErroCampo({ entrada: l.entrada, erro: l.erro }, repetida ? `Esta opção repete a opção ${LETRAS[textos.indexOf(textos[i])]}.` : '');
      l.entrada.setAttribute('aria-describedby', [repetida ? l.erro.id : null, l.contador.id].filter(Boolean).join(' '));
    });
    if (salvar) salvar.disabled = !valida();
  }

  const editor = { sujo: () => JSON.stringify(ler()) !== original, fechar: fecharEditor };
  editores.abrir(editor);
  const recarregar = async () => {
    editores.soltar(editor);
    await carregar('editor-pergunta:enunciado');
  };

  salvar = botaoSalvar('Salvar pergunta', async () => {
    limparErros(resumo, campos);
    const corpo = nova ? ler() : { ...ler(), atualizado_em: pergunta.atualizado_em };
    const resposta = await api(nova ? '/perguntas' : `/perguntas/${pergunta.id}`, { metodo: nova ? 'POST' : 'PUT', corpo });
    if (!resposta.ok) {
      mostrarFalha(resposta, { resumo, campos, aoRecarregar: recarregar });
      return;
    }
    editores.soltar(editor);
    estado.editor = undefined;
    toast('Pergunta salva');
    await carregar(`pergunta:${resposta.dados.id}:editar`);
  }, valida);
  atualizar();

  const esquerda = el('div', { class: 'flori-ct-acoes' },
    nova ? null : setas({
      nome: 'pergunta', numero: posicao + 1, posicao, total, chave: `pergunta:${pergunta.id}`,
      aoMover: (direcao) => mover(pergunta.id, direcao),
    }),
    botao('Visualizar', {
      onclick: () => previaPergunta({
        id: pergunta.id || 'previa', enunciado: campos.enunciado.entrada.value,
        opcoes: opcoes.map((o, i) => ({ id: o.id || `previa${i}`, texto: o.texto })),
      }),
    }));

  editor.mostrarFalha = (resposta) => mostrarFalha(resposta, { resumo, campos, aoRecarregar: recarregar });
  return el('div', { class: 'flori-ct-editor flori-ct-editor-pergunta', role: 'group', 'aria-label': nova ? 'Nova pergunta' : 'Editar pergunta' },
    resumo,
    el('p', { class: 'flori-ct-ajuda', text: 'Cada pergunta tem 4 opções e exatamente 1 correta. Enunciado e opções são salvos juntos.' }),
    campos.enunciado.bloco,
    el('fieldset', { class: 'flori-ct-campo' },
      el('legend', { class: 'form-label', text: 'Opções (marque a correta)' }),
      linhas.map((l) => l.bloco),
      erroOpcoes),
    el('div', { class: 'flori-ct-rodape' },
      esquerda,
      el('div', { class: 'flori-ct-acoes' }, botao('Cancelar', { onclick: () => editores.liberar() }), salvar)));
}

async function alternarSituacao(pergunta) {
  const ativar = !pergunta.ativo;
  const resposta = await executarAcao({
    caminho: `/perguntas/${pergunta.id}/${ativar ? 'ativar' : 'desativar'}`,
    caixa: estado.mensagem,
    sucesso: `Pergunta ${ativar ? 'ativada' : 'desativada'}`,
    depois: () => carregar(`pergunta:${pergunta.id}:situacao`),
  });
  if (resposta && !resposta.ok && resposta.dados.campos) {
    mostrarMensagem(estado.mensagem, '');
    estado.editor = pergunta.id;
    estado.falha = () => editores.atual()?.mostrarFalha?.(resposta);
    renderizar();
  }
}

async function mover(id, direcao) {
  await executarAcao({
    caminho: `/perguntas/${id}/reordenar`, corpo: { direcao }, caixa: estado.mensagem,
    depois: () => carregar(`pergunta:${id}:${direcao}`),
  });
}

async function restaurar(id) {
  await executarAcao({
    caminho: `/perguntas/${id}/restaurar`, caixa: estado.mensagem, sucesso: 'Pergunta restaurada',
    depois: () => carregar(),
  });
}

async function excluir(pergunta) {
  if (!(await editores.liberar())) return;
  const resposta = await api(`/perguntas/${pergunta.id}/impacto`);
  if (!resposta.ok) {
    mostrarMensagem(estado.mensagem, resposta.dados.mensagem || SEM_CONEXAO);
    return;
  }
  const n = resposta.dados.pessoas_responderam;
  let pessoas = `${n} pessoas já responderam esta pergunta.`;
  if (n === 1) pessoas = '1 pessoa já respondeu esta pergunta.';
  if (n === 0) pessoas = 'Ninguém respondeu esta pergunta ainda.';
  const sim = await confirmar({
    titulo: `Excluir a pergunta "${pergunta.enunciado}"?`,
    texto: `Ela deixa de aparecer nas próximas tentativas do quiz. ${pessoas}`,
    itens: [
      'Notas e certificados já emitidos não mudam.',
      'Se sobrarem menos de 10 ativas, o quiz continua com as que sobrarem e a nota é calculada sobre elas.',
      'Se não sobrar nenhuma ativa, o quiz fica indisponível.',
      'A pergunta fica guardada e pode ser restaurada.',
    ],
  });
  if (!sim) return;
  await executarAcao({
    caminho: `/perguntas/${pergunta.id}/excluir`, caixa: estado.mensagem, sucesso: 'Pergunta excluída',
    depois: () => carregar(),
  });
}
