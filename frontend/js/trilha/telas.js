import {
  barra, dataLonga, esc, flor, ICONE_CADEADO, ICONE_OK, ICONE_QUIZ, ICONE_SELO,
} from '../compartilhado/componentes.js';

const pluralCards = (n) => `${n} ${n === 1 ? 'card' : 'cards'}`;

const pluralPerguntas = (n) => `${n} ${n === 1 ? 'pergunta' : 'perguntas'}`;

function quizEmAtualizacao(quiz) {
  return `<div class="flori-quiz-card is-bloqueado">
    <span class="flori-quiz-icone">${ICONE_CADEADO}</span>
    <div class="flori-quiz-texto"><h2 class="flori-heading">Quiz final</h2>
      <p>${esc(quiz.mensagem || 'Quiz em atualização')}. Volte daqui a pouco.</p></div></div>`;
}

function cartaoQuiz(dados) {
  const { quiz, certificado, concluidos, total_cards: total } = dados;

  if (dados.modo_visualizacao) {
    if (!quiz.disponivel) return quizEmAtualizacao(quiz);
    return `<div class="flori-quiz-card is-liberado">
      <span class="flori-quiz-icone">${ICONE_QUIZ}</span>
      <div class="flori-quiz-texto"><h2 class="flori-heading">Quiz final</h2>
        <p>Cada tentativa mostra ${pluralPerguntas(quiz.total_perguntas)}. No modo visualização, as perguntas aparecem só para leitura, sem envio.</p></div>
      <div class="flori-quiz-acoes"><button type="button" class="btn btn-flori" data-ir="quiz">Ver as perguntas</button></div></div>`;
  }
  if (certificado) {
    const refazer = quiz.disponivel || quiz.em_andamento
      ? `<button type="button" class="btn btn-flori-outline" data-ir="quiz">${quiz.em_andamento ? 'Continuar o quiz' : 'Refazer o quiz'}</button>` : '';
    return `<div class="flori-quiz-card is-liberado">
      <span class="flori-quiz-icone">${ICONE_SELO}</span>
      <div class="flori-quiz-texto"><h2 class="flori-heading">Certificado emitido</h2>
        <p>Você passou no quiz com ${certificado.aproveitamento_percentual}% de aproveitamento.</p></div>
      <div class="flori-quiz-acoes">
        <button type="button" class="btn btn-flori" data-ir="certificado">Ver certificado</button>
        ${refazer}
      </div></div>`;
  }
  if (!quiz.liberado) {
    return `<div class="flori-quiz-card is-bloqueado">
      <span class="flori-quiz-icone">${ICONE_CADEADO}</span>
      <div class="flori-quiz-texto"><h2 class="flori-heading">Quiz final</h2>
        <p>Conclua todos os cards para liberar o quiz e ganhar o certificado. Faltam ${total - concluidos}.</p></div></div>`;
  }
  if (!quiz.disponivel && !quiz.em_andamento) return quizEmAtualizacao(quiz);
  const ultimo = quiz.tentativas ? ` Último resultado: ${quiz.ultimo_acertos} de ${quiz.ultimo_total}.` : '';
  let rotulo = quiz.tentativas ? 'Tentar de novo' : 'Começar o quiz';
  if (quiz.em_andamento) rotulo = 'Continuar o quiz';
  return `<div class="flori-quiz-card is-liberado">
    <span class="flori-quiz-icone">${ICONE_QUIZ}</span>
    <div class="flori-quiz-texto"><h2 class="flori-heading">Quiz final</h2>
      <p>${pluralPerguntas(quiz.total_perguntas)}. Com ${quiz.nota_minima_percentual}% de acertos, você recebe o certificado.${ultimo}</p></div>
    <div class="flori-quiz-acoes"><button type="button" class="btn btn-flori" data-ir="quiz">${rotulo}</button></div></div>`;
}

export function botaoGuia(guia, indice) {
  return `
    <button type="button" class="flori-socorro" data-socorro="${indice}">
      ${flor('#EDBFD8', 44, 'flori-socorro-flor')}
      <span class="flori-socorro-texto">
        <span class="flori-heading flori-socorro-titulo">${esc(guia.titulo)}</span>
        <span class="flori-socorro-sub">Um guia rápido com o que fazer agora.</span>
      </span>
      <span class="flori-socorro-acao">Abrir</span>
    </button>`;
}

export function telaTrilha(dados) {
  const guias = (dados.guias_rapidos || []).map(botaoGuia).join('');

  const leitura = dados.modo_visualizacao;
  const assuntos = dados.assuntos.map((a) => {
    const acao = leitura ? 'Ver' : a.concluidos === 0 ? 'Começar' : a.concluidos === a.total ? 'Revisar' : 'Continuar';
    const pe = leitura ? pluralCards(a.total) : `${a.concluidos} de ${pluralCards(a.total)}`;
    return `<a class="flori-assunto" href="#trilha/${a.id}" style="--cor:${esc(a.cor)}">
      ${flor(a.cor, 56)}
      <h2 class="flori-heading">${esc(a.titulo)}</h2>
      <p>${esc(a.descricao)}</p>
      ${leitura ? '' : barra(a.concluidos, a.total)}
      <div class="flori-assunto-pe"><span>${pe}</span><span class="flori-assunto-acao">${acao}</span></div>
    </a>`;
  }).join('');

  const resumo = leitura ? '' : `<div class="flori-resumo">
      <div class="flori-progresso-rotulo"><span>Seu andamento na trilha</span><span>${dados.concluidos} de ${dados.total_cards} cards</span></div>
      ${barra(dados.concluidos, dados.total_cards)}
    </div>`;

  return `${guias}
    <h1 class="flori-heading flori-titulo">Trilha do conhecimento</h1>
    <p class="flori-hint">Escolha um assunto e leia no seu ritmo. Cada card leva menos de um minuto.</p>
    ${resumo}
    <div class="flori-grade flori-grade-assuntos">${assuntos}</div>
    ${cartaoQuiz(dados)}`;
}

export function secaoExtras(extras, abertos) {
  if (!extras || !extras.assuntos.length) return '';
  const blocos = extras.assuntos.map((a) => {
    const aberto = abertos.has(a.id);
    const cards = a.cards.map((c, i) => `
      <button type="button" class="flori-flashcard" style="--cor:${esc(a.cor)}" data-abrir-extra="${esc(a.id)}:${i}">
        <span class="flori-flashcard-numero">Card ${i + 1}</span>
        <h3 class="flori-heading">${esc(c.tema)}</h3>
      </button>`).join('');
    return `<div class="flori-extra" style="--cor:${esc(a.cor)}">
      <button type="button" class="flori-extra-topo" data-extra-alternar="${esc(a.id)}" aria-expanded="${aberto}" aria-controls="extra_${esc(a.id)}">
        ${flor(a.cor, 40)}
        <span class="flori-extra-texto">
          <span class="flori-heading flori-extra-titulo">${esc(a.titulo)}</span>
          <span class="flori-extra-sub">${esc(a.descricao)}</span>
        </span>
        <span class="flori-extra-meta">${pluralCards(a.cards.length)}</span>
      </button>
      <div class="flori-grade flori-grade-cards flori-extra-cards" id="extra_${esc(a.id)}"${aberto ? '' : ' hidden'}>${cards}</div>
    </div>`;
  }).join('');
  return `<section class="flori-extras" aria-labelledby="tituloExtras">
    <h2 class="flori-heading flori-extras-titulo" id="tituloExtras">Para ir além</h2>
    <p class="flori-hint">Conteúdos extras. Não contam para o quiz nem para o certificado.</p>
    ${blocos}
  </section>`;
}

export function telaAssunto(dados, assuntoId) {
  const a = dados.assuntos.find((x) => x.id === assuntoId);
  if (!a) return telaTrilha(dados);
  const leitura = dados.modo_visualizacao;

  const cards = a.cards.map((c, i) => `
    <button type="button" class="flori-flashcard${c.concluido ? ' is-ok' : ''}" style="--cor:${esc(a.cor)}" data-abrir="${a.id}:${i}">
      <span class="flori-flashcard-numero">Card ${i + 1}</span>
      <h3 class="flori-heading">${esc(c.tema)}</h3>
      ${leitura ? '' : `<span class="flori-chip${c.concluido ? ' is-ok' : ''}">${c.concluido ? `${ICONE_OK} Concluído` : 'Para ler'}</span>`}
    </button>`).join('');

  const resumo = leitura ? '' : `<div class="flori-resumo">
      <div class="flori-progresso-rotulo"><span>Andamento neste assunto</span><span>${a.concluidos} de ${a.total} cards</span></div>
      ${barra(a.concluidos, a.total)}
    </div>`;

  return `
    <div class="flori-voltar-linha"><a class="flori-nav-back" href="#trilha">← Trilha do conhecimento</a></div>
    <h1 class="flori-heading flori-titulo">${esc(a.titulo)}</h1>
    <p class="flori-hint">${esc(a.descricao)}</p>
    ${resumo}
    <div class="flori-grade flori-grade-cards">${cards}</div>`;
}

export function blocoPergunta(pergunta, marcada, leitura) {
  const opcoes = pergunta.opcoes.map((o) => `
    <label class="flori-opcao${marcada === o.id ? ' is-marcada' : ''}">
      <input type="radio" name="opcao" value="${esc(o.id)}" ${marcada === o.id ? 'checked' : ''}${leitura ? ' disabled' : ''}> <span>${esc(o.texto)}</span>
    </label>`).join('');
  return `<fieldset class="flori-pergunta">
        <legend id="perguntaTitulo" tabindex="-1">${esc(pergunta.enunciado)}</legend>
        ${opcoes}
      </fieldset>`;
}

export function telaQuiz(quiz, estado) {
  const perguntas = quiz.perguntas;
  const i = estado.indice;
  const pergunta = perguntas[i];
  const marcada = estado.respostas[pergunta.id];
  const ultima = i === perguntas.length - 1;

  let avancar = `<button type="button" class="btn btn-flori" id="btnProx" data-quiz="prox" ${marcada === undefined || estado.enviando ? 'disabled' : ''}>${ultima ? 'Ver resultado' : 'Próxima'}</button>`;
  if (estado.leitura) {
    avancar = ultima
      ? '<button type="button" class="btn btn-flori" data-ir="trilha">Voltar à trilha</button>'
      : '<button type="button" class="btn btn-flori" id="btnProx" data-quiz="prox">Próxima</button>';
  }

  return `
    <div class="flori-quiz">
      <div class="flori-voltar-linha"><a class="flori-nav-back" href="#trilha">← Sair do quiz</a></div>
      <h1 class="flori-heading flori-titulo">Quiz final</h1>
      <div class="flori-progresso-rotulo mt-3"><span>Pergunta ${i + 1} de ${perguntas.length}</span><span>Mínimo para o certificado: ${quiz.nota_minima_percentual}%</span></div>
      ${barra(i + 1, perguntas.length)}
      ${blocoPergunta(pergunta, marcada, estado.leitura)}
      <p class="flori-aviso-erro" role="alert">${estado.erro ? esc(estado.erro) : ''}</p>
      <div class="flori-quiz-botoes">
        <button type="button" class="btn btn-flori-outline" data-quiz="ant" ${i === 0 ? 'disabled' : ''}>Voltar</button>
        ${avancar}
      </div>
    </div>`;
}

export function telaResultado(r) {
  if (r.aprovada) {
    return `<div class="flori-quiz"><div class="flori-resultado">
      ${flor('#C9E372', 64)}
      <h1 class="flori-heading">Parabéns, você concluiu a trilha!</h1>
      <p class="flori-resultado-nota">${r.acertos} de ${r.total_perguntas} acertos (${r.percentual}%)</p>
      <p class="mb-0">Seu certificado está pronto.</p>
      <div class="flori-resultado-acoes">
        <button type="button" class="btn btn-flori" data-ir="certificado">Ver meu certificado</button>
        <button type="button" class="btn btn-flori-outline" data-ir="trilha">Voltar à trilha</button>
      </div></div></div>`;
  }

  const minimo = Math.ceil((r.total_perguntas * r.nota_minima_percentual) / 100);
  const revisar = r.assuntos_a_revisar.map((a) => `<li><a href="#trilha/${esc(a.id)}">${esc(a.titulo)}</a></li>`).join('');
  const destino = r.assuntos_a_revisar.length ? `trilha/${esc(r.assuntos_a_revisar[0].id)}` : 'trilha';
  const listaRevisar = revisar ? `<div class="flori-revisar">
      <strong>Que tal rever estes assuntos antes de tentar de novo?</strong>
      <ul>${revisar}</ul>
    </div>` : '';
  return `<div class="flori-quiz"><div class="flori-resultado">
    ${flor('#EDBFD8', 64)}
    <h1 class="flori-heading">Quase lá!</h1>
    <p class="flori-resultado-nota">${r.acertos} de ${r.total_perguntas} acertos (${r.percentual}%)</p>
    <p class="mb-0">Para o certificado, o mínimo é ${r.nota_minima_percentual}% (${minimo} de ${r.total_perguntas}).</p>
    ${listaRevisar}
    <div class="flori-resultado-acoes">
      <button type="button" class="btn btn-flori" data-ir="${destino}">Revisar os conteúdos</button>
      <button type="button" class="btn btn-flori-outline" data-ir="quiz">Tentar o quiz de novo</button>
    </div></div></div>`;
}

export function telaCertificado(c) {
  const horas = c.carga_horaria_minutos % 60 === 0
    ? `${c.carga_horaria_minutos / 60} ${c.carga_horaria_minutos === 60 ? 'hora' : 'horas'}`
    : `${c.carga_horaria_minutos} minutos`;

  return `
    <div class="flori-voltar-linha"><a class="flori-nav-back" href="#trilha">← Trilha do conhecimento</a></div>
    <h1 class="flori-heading flori-titulo mb-3">Seu certificado</h1>
    <div class="flori-cert-wrap">
      <div class="flori-certificado">
        ${flor('#EDBFD8', 120, 'flori-cert-canto tl')}
        ${flor('#C9E372', 120, 'flori-cert-canto br')}
        <div class="flori-cert-marca">${flor('#EDBFD8', 36, 'flori-cert-logo')}<span>flori</span></div>
        <h2 class="flori-heading flori-cert-titulo">Certificado de conclusão</h2>
        <p class="flori-cert-texto">Certificamos que</p>
        <div class="flori-cert-nome">${esc(c.nome_completo)}</div>
        <p class="flori-cert-texto mb-0">concluiu a</p>
        <p class="flori-cert-trilha">${esc(c.trilha)}</p>
        <div class="flori-cert-dados">
          <div><b>Carga horária</b>${horas}</div>
          <div><b>Aproveitamento no quiz</b>${c.aproveitamento_percentual}%</div>
          <div><b>Emitido em</b>${dataLonga(c.emitido_em)}</div>
        </div>
        <p class="flori-cert-codigo">Código de verificação: ${esc(c.codigo)}</p>
      </div>
      <div class="flori-cert-acoes">
        <button type="button" class="btn btn-flori" data-imprimir>Baixar certificado (PDF)</button>
        <button type="button" class="btn btn-flori-outline" data-ir="trilha">Voltar à trilha</button>
      </div>
    </div>`;
}
