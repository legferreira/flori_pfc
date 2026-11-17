import { auth } from './firebase.js';
import { paginasDoMenu } from './navegacao.js';
import { desenharRodape } from './rodape.js';
import { perguntarSituacao, situacaoAdiada } from './saude.js';
import { signOut } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js';

function itemDeNavegacao(pagina, ativa) {
  const atual = pagina.id === ativa ? ' aria-current="page"' : '';
  return `<a class="flori-nav-item" href="${pagina.href}"${atual}>
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">${pagina.icone}</svg>
    <span>${pagina.rotulo}</span></a>`;
}

function desenharTopo(paginaAtiva) {
  document.getElementById('topo').innerHTML = `
    <a href="home.html" class="flori-mark mb-0" style="text-decoration: none;">
      <svg width="24" height="24" viewBox="0 0 28 28" fill="none" aria-hidden="true">
        <circle cx="14" cy="8" r="5" fill="#EDBFD8"/><circle cx="20" cy="14" r="5" fill="#C9E372"/>
        <circle cx="14" cy="20" r="5" fill="#CDD98D"/><circle cx="8" cy="14" r="5" fill="#EDBFD8"/>
        <circle cx="14" cy="14" r="3.5" fill="#3E2F59"/>
      </svg>
      <span>flori</span>
    </a>
    <nav class="flori-nav" aria-label="Principal">${paginasDoMenu(null).map((p) => itemDeNavegacao(p, paginaAtiva)).join('')}</nav>
    <div class="flori-usuario">
      <a class="flori-usuario-link" href="perfil.html" aria-label="Meu perfil"${paginaAtiva === 'perfil' ? ' aria-current="page"' : ''}>
        <img class="flori-avatar" id="fotoUsuario" alt="" referrerpolicy="no-referrer" hidden>
        <span class="flori-avatar flori-avatar-inicial" id="inicialUsuario" aria-hidden="true" hidden></span>
        <span class="flori-usuario-nome" id="nomeUsuario"></span>
      </a>
      <button type="button" class="btn btn-flori-outline btn-sair" id="botaoSair">Sair</button>
    </div>`;
  document.getElementById('botaoSair').addEventListener('click', sair);
}

function mostrarPerfil(perfil) {
  const foto = document.getElementById('fotoUsuario');
  const inicial = document.getElementById('inicialUsuario');
  const mostrarInicial = () => {
    foto.hidden = true;
    inicial.textContent = (perfil.apelido || '?').trim().charAt(0).toUpperCase();
    inicial.hidden = false;
  };

  document.getElementById('nomeUsuario').textContent = perfil.apelido;
  if (perfil.foto_url) {
    foto.onerror = mostrarInicial;
    foto.src = perfil.foto_url;
    foto.alt = `Foto de ${perfil.apelido}`;
    foto.hidden = false;
  } else {
    mostrarInicial();
  }
}

const DOCUMENTOS = {
  termos_uso: { href: 'termos-de-uso.html', rotulo: 'Termos de Uso' },
  politica_privacidade: { href: 'politica-privacidade.html', rotulo: 'Política de Privacidade' },
};
const CHAVE_AVISO_DOCUMENTOS = 'flori_aviso_documentos_dispensado';

function lerDispensa() {
  try { return sessionStorage.getItem(CHAVE_AVISO_DOCUMENTOS); } catch { return null; }
}

function gravarDispensa(valor) {
  try { sessionStorage.setItem(CHAVE_AVISO_DOCUMENTOS, valor); } catch {}
}

function mostrarAvisoDocumentos(perfil) {
  const pendentes = (perfil.documentos_desatualizados || []).filter((tipo) => DOCUMENTOS[tipo]);
  const assinatura = pendentes.join(',');
  if (!pendentes.length || lerDispensa() === assinatura) return;

  const links = pendentes
    .map((tipo) => `<a href="${DOCUMENTOS[tipo].href}">${DOCUMENTOS[tipo].rotulo}</a>`).join(' e ');
  const aviso = document.createElement('div');
  aviso.className = 'container';
  aviso.innerHTML = `<div class="flori-aviso-documentos" role="status">
    <span>Atualizamos nossos Termos de Uso e nossa Política de Privacidade. Veja: ${links}.
      <small class="flori-aviso-erro" hidden></small></span>
    <div class="flori-aviso-acoes">
      <button type="button" class="btn btn-flori btn-flori-sm" data-aceitar>Li e aceito</button>
      <button type="button" class="btn btn-flori-outline btn-flori-sm" data-dispensar>Dispensar</button>
    </div></div>`;
  aviso.querySelector('[data-dispensar]').addEventListener('click', () => {
    gravarDispensa(assinatura);
    aviso.remove();
  });
  aviso.querySelector('[data-aceitar]').addEventListener('click', async (evento) => {
    const botao = evento.currentTarget;
    const erro = aviso.querySelector('.flori-aviso-erro');
    botao.disabled = true;
    erro.hidden = true;
    try {
      const { ok, dados } = await chamarApi('/perfil/documentos/aceitar', { metodo: 'POST' });
      if (!ok) throw new Error(dados.mensagem);
      if ((dados.documentos_desatualizados || []).length) throw new Error();
      aviso.remove();
    } catch (falha) {
      erro.textContent = falha.message || 'Não foi possível registrar o aceite. Tente de novo.';
      erro.hidden = false;
      botao.disabled = false;
    }
  });
  document.getElementById('conteudo').insertAdjacentElement('beforebegin', aviso);
}

function ajustarNavegacao(perfil, paginaAtiva) {
  const nav = document.querySelector('.flori-nav');
  nav.innerHTML = paginasDoMenu(perfil).map((p) => itemDeNavegacao(p, paginaAtiva)).join('');
  if (perfil.perfil === 'admin') document.querySelector('.flori-mark').setAttribute('href', 'admin.html');
}

function perguntarSituacaoSeFaltar(perfil, paginaAtiva) {
  if (perfil.perfil !== 'user' || perfil.situacao_menstrual || situacaoAdiada()) return;
  perguntarSituacao({ temConsentimento: Boolean(perfil.consentimento_saude?.aceito) }).then((estado) => {
    if (!estado) return;
    Object.assign(perfil, {
      situacao_menstrual: estado.situacao,
      diario_disponivel: estado.diario_disponivel,
      consentimento_saude: { ...(perfil.consentimento_saude || {}), aceito: estado.consentimento_saude },
    });
    ajustarNavegacao(perfil, paginaAtiva);
    window.dispatchEvent(new CustomEvent('flori:situacao', { detail: estado }));
  });
}

export async function finalizarSessao(destino = 'index.html') {
  await encerrarSessao();
  try { await signOut(auth); } catch {}
  window.location.replace(destino);
}

async function sair(evento) {
  evento.currentTarget.disabled = true;
  await finalizarSessao();
}

function voltarParaLogin() {
  window.location.replace('login.html');
}

export async function chamarApi(caminho, { metodo = 'GET', corpo } = {}) {
  const opcoes = { method: metodo, headers: { Authorization: `Bearer ${tokenDaSessao()}` } };
  if (corpo !== undefined) {
    opcoes.headers['Content-Type'] = 'application/json';
    opcoes.body = JSON.stringify(corpo);
  }

  const resposta = await fetch(`${API_SESSAO}${caminho}`, opcoes);
  if (resposta.status === 401) {
    await encerrarSessao();
    voltarParaLogin();
    return new Promise(() => {});
  }
  const dados = await resposta.json().catch(() => ({}));
  return { ok: resposta.ok, status: resposta.status, dados };
}

export async function iniciarAreaLogada(paginaAtiva) {
  if (!tokenDaSessao()) {
    voltarParaLogin();
    return null;
  }

  desenharTopo(paginaAtiva);
  desenharRodape({ classeExtra: 'flori-rodape-logado' });
  let perfil;
  try {
    perfil = (await chamarApi('/perfil')).dados;
  } catch {
    perfil = { apelido: localStorage.getItem('flori_apelido') || '' };
  }

  mostrarPerfil(perfil);
  ajustarNavegacao(perfil, paginaAtiva);
  mostrarAvisoDocumentos(perfil);
  perguntarSituacaoSeFaltar(perfil, paginaAtiva);
  document.getElementById('topo').hidden = false;
  document.getElementById('conteudo').hidden = false;
  return perfil;
}
