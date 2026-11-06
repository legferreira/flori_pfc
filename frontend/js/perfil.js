import { chamarApi, iniciarAreaLogada } from './compartilhado/area-logada.js';
import { dataLonga, esc } from './compartilhado/componentes.js';

const painel = document.getElementById('painel');
const LIMITES = { nome: 100, sobrenome: 100, apelido: 50 };

let perfil = null;
let revogando = null;

function blocoConsentimento(c) {
  const situacao = c.aceito
    ? `Aceito em ${dataLonga(c.data)} (versão ${esc(c.versao_documento)})`
    : `Revogado em ${dataLonga(c.data)}`;

  let acoes;
  if (!c.aceito) {
    acoes = `<button type="button" class="btn btn-flori btn-flori-sm" data-reativar="${c.tipo}">Reativar</button>`;
  } else if (revogando === c.tipo) {
    acoes = `<button type="button" class="btn btn-flori btn-flori-sm" data-confirmar-revogar="${c.tipo}">Confirmar revogação</button>
      <button type="button" class="btn btn-flori-outline btn-flori-sm" data-cancelar>Cancelar</button>`;
  } else {
    acoes = `<button type="button" class="btn btn-flori-outline btn-flori-sm" data-revogar="${c.tipo}">Revogar</button>`;
  }

  return `<div class="flori-consentimento">
    <strong>${esc(c.rotulo)}</strong><small class="flori-hint">${situacao}</small>
    <div class="flori-consentimento-acoes">${acoes}</div></div>`;
}

function desenhar() {
  painel.innerHTML = `<div class="flori-perfil">
    <section class="flori-card flori-perfil-bloco" aria-label="Dados pessoais">
      <h2 class="flori-heading">Dados pessoais</h2>
      <form id="formPerfil" novalidate>
        <div class="row g-2 mb-3">
          <div class="col-sm-6"><label class="form-label" for="nome">Nome</label>
            <input type="text" class="form-control" id="nome" value="${esc(perfil.nome)}" autocomplete="given-name" required></div>
          <div class="col-sm-6"><label class="form-label" for="sobrenome">Sobrenome</label>
            <input type="text" class="form-control" id="sobrenome" value="${esc(perfil.sobrenome)}" autocomplete="family-name" required></div>
        </div>
        <div class="mb-3"><label class="form-label" for="apelido">Como prefere ser chamada</label>
          <input type="text" class="form-control" id="apelido" value="${esc(perfil.apelido)}" autocomplete="nickname"></div>
        <div class="mb-3"><label class="form-label" for="celular">Celular <span class="flori-hint">(opcional)</span></label>
          <input type="tel" class="form-control" id="celular" value="${esc(perfil.celular || '')}" placeholder="(11) 90000-0000" autocomplete="tel"></div>
        <div class="row g-2 mb-3">
          <div class="col-sm-7"><label class="form-label" for="email">E-mail</label>
            <input type="email" class="form-control" id="email" value="${esc(perfil.email || '')}" readonly></div>
          <div class="col-sm-5"><label class="form-label" for="nascimento">Nascimento</label>
            <input type="text" class="form-control" id="nascimento" value="${esc(perfil.data_nascimento)}" readonly></div>
        </div>
        <p class="flori-hint mb-3">E-mail e data de nascimento não podem ser alterados por aqui.</p>
        <button type="submit" class="btn btn-flori" id="botaoSalvar">Salvar alterações</button>
        <div class="flori-error" id="erroPerfil" role="alert"></div>
        <div class="flori-success" id="sucessoPerfil" role="status"></div>
      </form>
    </section>
    <section class="flori-card flori-perfil-bloco" aria-label="Consentimentos">
      <h2 class="flori-heading">Seus consentimentos</h2>
      <p class="flori-hint">Ao revogar, o Flori deixa de tratar seus dados: a trilha e o dashboard ficam bloqueados até você reativar.</p>
      ${perfil.consentimentos.map(blocoConsentimento).join('')}
      <div class="flori-error" id="erroConsentimento" role="alert"></div>
    </section>
  </div>`;
}

function mostrar(id, texto) {
  const el = document.getElementById(id);
  el.textContent = texto;
  el.style.display = texto ? 'block' : 'none';
}

function validar(dados) {
  if (!dados.nome || !dados.sobrenome) return 'Preencha o nome e o sobrenome.';
  for (const [campo, maximo] of Object.entries(LIMITES)) {
    if (dados[campo].length > maximo) return `O campo ${campo} aceita no máximo ${maximo} caracteres.`;
  }
  const digitos = dados.celular.replace(/\D/g, '').length;
  if (dados.celular && (digitos < 10 || digitos > 13)) return 'Celular inválido. Informe o DDD e o número.';
  return '';
}

async function salvar(evento) {
  evento.preventDefault();
  mostrar('erroPerfil', '');
  mostrar('sucessoPerfil', '');

  const dados = ['nome', 'sobrenome', 'apelido', 'celular'].reduce((acc, campo) => {
    acc[campo] = document.getElementById(campo).value.trim();
    return acc;
  }, {});

  const problema = validar(dados);
  if (problema) { mostrar('erroPerfil', problema); return; }

  const botao = document.getElementById('botaoSalvar');
  botao.disabled = true;
  try {
    const { ok, dados: corpo } = await chamarApi('/perfil', { metodo: 'PATCH', corpo: dados });
    if (!ok) { mostrar('erroPerfil', corpo.mensagem || 'Não foi possível salvar.'); return; }
    perfil = corpo;
    localStorage.setItem('flori_apelido', perfil.apelido);
    document.getElementById('nomeUsuario').textContent = perfil.apelido;
    desenhar();
    mostrar('sucessoPerfil', 'Dados atualizados.');
  } catch {
    mostrar('erroPerfil', 'Sem conexão com o servidor. Tente de novo.');
  } finally {
    botao.disabled = false;
  }
}

async function alterarConsentimento(tipo, aceito) {
  revogando = null;
  try {
    const { ok, dados: corpo } = await chamarApi('/perfil/consentimentos', { metodo: 'POST', corpo: { tipo, aceito } });
    if (!ok) throw new Error(corpo.mensagem);
    perfil = corpo;
    desenhar();
  } catch (erro) {
    desenhar();
    mostrar('erroConsentimento', erro.message || 'Sem conexão com o servidor. Tente de novo.');
  }
}

painel.addEventListener('submit', (e) => { if (e.target.id === 'formPerfil') salvar(e); });

painel.addEventListener('click', (e) => {
  const alvo = (atributo) => e.target.closest(`[${atributo}]`);
  if (alvo('data-revogar')) { revogando = alvo('data-revogar').dataset.revogar; desenhar(); }
  else if (alvo('data-cancelar')) { revogando = null; desenhar(); }
  else if (alvo('data-confirmar-revogar')) alterarConsentimento(alvo('data-confirmar-revogar').dataset.confirmarRevogar, false);
  else if (alvo('data-reativar')) alterarConsentimento(alvo('data-reativar').dataset.reativar, true);
});

async function carregar() {
  try {
    const { ok, dados } = await chamarApi('/perfil');
    if (!ok) throw new Error(dados.mensagem || 'Não foi possível carregar o perfil.');
    perfil = dados;
    desenhar();
  } catch (erro) {
    painel.innerHTML = `<div class="flori-card text-center"><p class="mb-3">${esc(erro.message || 'Sem conexão com o servidor.')}</p>
      <button type="button" class="btn btn-flori btn-flori-sm" id="tentarDeNovo">Tentar de novo</button></div>`;
    document.getElementById('tentarDeNovo').addEventListener('click', carregar);
  }
}

if (await iniciarAreaLogada('perfil')) carregar();
