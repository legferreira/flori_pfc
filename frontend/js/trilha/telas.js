import {
  barra, dataLonga, esc, flor, ICONE_CADEADO, ICONE_OK, ICONE_QUIZ, ICONE_SELO, percentual,
} from '../compartilhado/componentes.js';

const pluralCards = (n) => `${n} ${n === 1 ? 'card' : 'cards'}`;

function cartaoQuiz(dados) {
  const { quiz, certificado, concluidos, total_cards: total, trilha } = dados;

  if (certificado) {
    return `<div class="flori-quiz-card is-liberado">
      <span class="flori-quiz-icone">${ICONE_SELO}</span>
      <div class="flori-quiz-texto"><h2 class="flori-heading">Certificado emitido</h2>
        <p>Você passou no quiz com ${certificado.aproveitamento_percentual}% de aproveitamento.</p></div>
      <div class="flori-quiz-acoes">
        <button type="button" class="btn btn-flori" data-ir="certificado">Ver certificado</button>
        <button type="button" class="btn btn-flori-outline" data-ir="quiz">Refazer o quiz</button>
      </div></div>`;
  }
  if (!quiz.liberado) {
    return `<div class="flori-quiz-card is-bloqueado">
      <span class="flori-quiz-icone">${ICONE_CADEADO}</span>
      <div class="flori-quiz-texto"><h2 class="flori-heading">Quiz final</h2>
        <p>Conclua todos os cards para liberar o quiz e ganhar o certificado. Faltam ${total - concluidos}.</p></div></div>`;
  }
  const ultimo = quiz.tentativas ? ` Último resultado: ${quiz.ultimo_acertos} de ${quiz.total_perguntas}.` : '';
  return `<div class="flori-quiz-card is-liberado">
    <span class="flori-quiz-icone">${ICONE_QUIZ}</span>
    <div class="flori-quiz-texto"><h2 class="flori-heading">Quiz final</h2>
      <p>${quiz.total_perguntas} perguntas. Com ${trilha.nota_minima_percentual}% de acertos, você recebe o certificado.${ultimo}</p></div>
    <div class="flori-quiz-acoes"><button type="button" class="btn btn-flori" data-ir="quiz">${quiz.tentativas ? 'Tentar de novo' : 'Começar o quiz'}</button></div></div>`;
}

export function telaTrilha(dados) {
  const guia = dados.guia_rapido;
  const botaoGuia = guia ? `
    <button type="button" class="flori-socorro" data-socorro>
      ${flor('#EDBFD8', 44, 'flori-socorro-flor')}
      <span class="flori-socorro-texto">
        <span class="flori-heading flori-socorro-titulo">${esc(guia.titulo)}</span>
        <span class="flori-socorro-sub">Um guia rápido com o que fazer agora.</span>
      </span>
      <span class="flori-socorro-acao">Abrir</span>
    </button>` : '';

  const assuntos = dados.assuntos.map((a) => {
    const acao = a.concluidos === 0 ? 'Começar' : a.concluidos === a.total ? 'Revisar' : 'Continuar';
    return `<a class="flori-assunto" href="#trilha/${a.id}" style="--cor:${esc(a.cor)}">
      ${flor(a.cor, 56)}
      <h2 class="flori-heading">${esc(a.titulo)}</h2>
      <p>${esc(a.descricao)}</p>
      ${barra(a.concluidos, a.total)}
      <div class="flori-assunto-pe"><span>${a.concluidos} de ${pluralCards(a.total)}</span><span class="flori-assunto-acao">${acao}</span></div>
    </a>`;
  }).join('');

  return `${botaoGuia}
    <h1 class="flori-heading flori-titulo">Trilha do conhecimento</h1>
    <p class="flori-hint">Escolha um assunto e leia no seu ritmo. Cada card leva menos de um minuto.</p>
    <div class="flori-resumo">
      <div class="flori-progresso-rotulo"><span>Seu andamento na trilha</span><span>${dados.concluidos} de ${dados.total_cards} cards</span></div>
      ${barra(dados.concluidos, dados.total_cards)}
    </div>
    <div class="flori-grade flori-grade-assuntos">${assuntos}</div>
    ${cartaoQuiz(dados)}`;
}

export function telaAssunto(dados, assuntoId) {
  const a = dados.assuntos.find((x) => x.id === assuntoId);
  if (!a) return telaTrilha(dados);

  const cards = a.cards.map((c, i) => `
    <button type="button" class="flori-flashcard${c.concluido ? ' is-ok' : ''}" style="--cor:${esc(a.cor)}" data-abrir="${a.id}:${i}">
      <span class="flori-flashcard-numero">Card ${i + 1}</span>
      <h3 class="flori-heading">${esc(c.tema)}</h3>
      <span class="flori-chip${c.concluido ? ' is-ok' : ''}">${c.concluido ? `${ICONE_OK} Concluído` : 'Para ler'}</span>
    </button>`).join('');

  return `
    <div class="flori-voltar-linha"><a class="flori-nav-back" href="#trilha">← Trilha do conhecimento</a></div>
    <h1 class="flori-heading flori-titulo">${esc(a.titulo)}</h1>
    <p class="flori-hint">${esc(a.descricao)}</p>
    <div class="flori-resumo">
      <div class="flori-progresso-rotulo"><span>Andamento neste assunto</span><span>${a.concluidos} de ${a.total} cards</span></div>
      ${barra(a.concluidos, a.total)}
    </div>
    <div class="flori-grade flori-grade-cards">${cards}</div>`;
}

export function telaQuiz(quiz, estado) {
  const perguntas = quiz.perguntas;
  const i = estado.indice;
  const pergunta = perguntas[i];
  const marcada = estado.respostas[pergunta.id];

  const opcoes = pergunta.opcoes.map((o) => `
    <label class="flori-opcao${marcada === o.id ? ' is-marcada' : ''}">
      <input type="radio" name="opcao" value="${o.id}" ${marcada === o.id ? 'checked' : ''}> <span>${esc(o.texto)}</span>
    </label>`).join('');

  return `
    <div class="flori-quiz">
      <div class="flori-voltar-linha"><a class="flori-nav-back" href="#trilha">← Sair do quiz</a></div>
      <h1 class="flori-heading flori-titulo">Quiz final</h1>
      <div class="flori-progresso-rotulo mt-3"><span>Pergunta ${i + 1} de ${perguntas.length}</span><span>Mínimo para o certificado: ${quiz.nota_minima_percentual}%</span></div>
      ${barra(i + 1, perguntas.length)}
      <fieldset class="flori-pergunta">
        <legend id="perguntaTitulo" tabindex="-1">${esc(pergunta.enunciado)}</legend>
        ${opcoes}
      </fieldset>
      <p class="flori-aviso-erro" role="alert">${estado.erro ? esc(estado.erro) : ''}</p>
      <div class="flori-quiz-botoes">
        <button type="button" class="btn btn-flori-outline" data-quiz="ant" ${i === 0 ? 'disabled' : ''}>Voltar</button>
        <button type="button" class="btn btn-flori" id="btnProx" data-quiz="prox" ${marcada === undefined || estado.enviando ? 'disabled' : ''}>${i === perguntas.length - 1 ? 'Ver resultado' : 'Próxima'}</button>
      </div>
    </div>`;
}

export function telaResultado(r) {
  if (r.aprovada) {
    return `<div class="flori-quiz"><div class="flori-resultado">
      ${flor('#C9E372', 64)}
      <h1 class="flori-heading">Parabéns, você concluiu a trilha!</h1>
      <p class="flori-resultado-nota">${r.acertos} de ${r.total}</p>
      <p class="mb-0">${r.percentual}% de aproveitamento. Seu certificado está pronto.</p>
      <div class="flori-resultado-acoes">
        <button type="button" class="btn btn-flori" data-ir="certificado">Ver meu certificado</button>
        <button type="button" class="btn btn-flori-outline" data-ir="trilha">Voltar à trilha</button>
      </div></div></div>`;
  }

  const minimo = Math.ceil((r.total * r.nota_minima_percentual) / 100);
  const revisar = r.assuntos_a_revisar.map((a) => `<li><a href="#trilha/${a.id}">${esc(a.titulo)}</a></li>`).join('');
  return `<div class="flori-quiz"><div class="flori-resultado">
    ${flor('#EDBFD8', 64)}
    <h1 class="flori-heading">Quase lá!</h1>
    <p class="flori-resultado-nota">${r.acertos} de ${r.total}</p>
    <p class="mb-0">${r.percentual}% de aproveitamento. Para o certificado, o mínimo é ${r.nota_minima_percentual}% (${minimo} de ${r.total}).</p>
    <div class="flori-revisar">
      <strong>Que tal rever estes assuntos antes de tentar de novo?</strong>
      <ul>${revisar}</ul>
    </div>
    <div class="flori-resultado-acoes">
      <button type="button" class="btn btn-flori" data-ir="trilha/${r.assuntos_a_revisar[0].id}">Revisar os conteúdos</button>
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
