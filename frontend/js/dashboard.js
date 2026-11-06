import { barra, esc } from './compartilhado/componentes.js';
import { chamarApi, iniciarAreaLogada } from './compartilhado/area-logada.js';

const painel = document.getElementById('painel');

function desenhar(d) {
  const linhas = d.assuntos.map((a) => `
    <div class="flori-linha-assunto" style="--cor:${esc(a.cor)}">
      <div class="flori-linha-topo"><strong>${esc(a.titulo)}</strong><span>${a.concluidos} de ${a.total} cards</span><em>${a.percentual}%</em></div>
      ${barra(a.concluidos, a.total)}
    </div>`).join('');

  const melhorNota = d.melhor_nota_percentual === null ? '–' : `${d.melhor_nota_percentual}%`;
  const numeros = [
    { valor: d.concluidos, rotulo: `cards concluídos de ${d.total}` },
    { valor: `${d.percentual}%`, rotulo: 'da trilha concluída' },
    { valor: d.tentativas, rotulo: 'tentativas no quiz' },
    { valor: melhorNota, rotulo: 'melhor nota no quiz' },
  ].map((n) => `<div class="flori-numero"><b>${n.valor}</b><span>${n.rotulo}</span></div>`).join('');

  painel.innerHTML = `<div class="flori-numeros" aria-label="Indicadores">${numeros}</div>
  <div class="flori-dash">
    <section class="flori-painel flori-grande" aria-label="Andamento geral">
      <div class="flori-rosca" style="--p:${d.percentual}" role="img" aria-label="${d.percentual}% da trilha concluída"><b>${d.percentual}%</b></div>
      <p><strong>da trilha concluída</strong><br>${d.concluidos} de ${d.total} cards</p>
    </section>
    <section class="flori-painel" aria-label="Andamento por assunto">
      <h2 class="flori-heading">Andamento por assunto</h2>
      ${linhas}
    </section>
  </div>`;
}

function mostrarErro(mensagem) {
  painel.innerHTML = `<div class="flori-card text-center"><p class="mb-3">${esc(mensagem)}</p>
    <button type="button" class="btn btn-flori btn-flori-sm" id="tentarDeNovo">Tentar de novo</button></div>`;
  document.getElementById('tentarDeNovo').addEventListener('click', carregar);
}

async function carregar() {
  try {
    const { ok, dados } = await chamarApi('/dashboard');
    if (!ok) throw new Error(dados.mensagem || 'Não foi possível carregar o dashboard.');
    desenhar(dados);
  } catch (erro) {
    mostrarErro(erro.message || 'Sem conexão com o servidor.');
  }
}

if (await iniciarAreaLogada('dashboard')) carregar();
