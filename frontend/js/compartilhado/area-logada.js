import { auth } from './firebase.js';
import { signOut } from 'https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js';

const PAGINAS = [
  { id: 'trilha', href: 'home.html', rotulo: 'Trilha', icone: '<circle cx="6" cy="18" r="2.5" stroke="currentColor" stroke-width="2"/><circle cx="18" cy="6" r="2.5" stroke="currentColor" stroke-width="2"/><path d="M8 17c5 0 3-5 8-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="1 4"/>' },
  { id: 'diario', href: 'diario.html', rotulo: 'Diário do corpo', breve: true, icone: '<path d="M6 4h11a1 1 0 0 1 1 1v15H7a1 1 0 0 1-1-1V4z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M9 9h6M9 13h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' },
  { id: 'dashboard', href: 'dashboard.html', rotulo: 'Dashboard', icone: '<path d="M5 20V11M12 20V5M19 20v-7" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>' },
];

function itemDeNavegacao(pagina, ativa) {
  const atual = pagina.id === ativa ? ' aria-current="page"' : '';
  const breve = pagina.breve ? '<span class="flori-breve">em breve</span>' : '';
  return `<a class="flori-nav-item" href="${pagina.href}"${atual}>
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">${pagina.icone}</svg>
    <span>${pagina.rotulo}</span>${breve}</a>`;
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
    <nav class="flori-nav" aria-label="Principal">${PAGINAS.map((p) => itemDeNavegacao(p, paginaAtiva)).join('')}</nav>
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

async function sair(evento) {
  evento.currentTarget.disabled = true;
  await encerrarSessao();
  try { await signOut(auth); } catch {}
  window.location.replace('index.html');
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
  let perfil;
  try {
    perfil = (await chamarApi('/perfil')).dados;
  } catch {
    perfil = { apelido: localStorage.getItem('flori_apelido') || '' };
  }

  mostrarPerfil(perfil);
  document.getElementById('topo').hidden = false;
  document.getElementById('conteudo').hidden = false;
  return perfil;
}
