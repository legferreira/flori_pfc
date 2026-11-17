import { chamarApi, finalizarSessao, iniciarAreaLogada } from './compartilhado/area-logada.js';
import { dataLonga, esc } from './compartilhado/componentes.js';
import { confirmar, perguntarSituacao, rotuloDaSituacao } from './compartilhado/saude.js';

const painel = document.getElementById('painel');
const LIMITES = { nome: 100, sobrenome: 100, apelido: 50 };

let perfil = null;
let revogando = null;

const DOCUMENTOS = {
  termos_uso: 'termos-de-uso.html',
  politica_privacidade: 'politica-privacidade.html',
};

const ICONE_EXTERNO = '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M9 3h4v4M13 3L7.5 8.5M11.5 9.5V12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1h2.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function tituloConsentimento(c) {
  const href = DOCUMENTOS[c.tipo];
  if (!href) return `<strong>${esc(c.rotulo)}</strong>`;
  return `<a class="flori-consentimento-link" href="${href}" target="_blank" rel="noopener">
    <strong>${esc(c.rotulo)}</strong><span class="flori-consentimento-icone" role="img" aria-label="Abrir em nova aba">${ICONE_EXTERNO}</span></a>`;
}

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
    ${tituloConsentimento(c)}<small class="flori-hint">${situacao}</small>
    <div class="flori-consentimento-acoes">${acoes}</div></div>`;
}

function acoesSaude(c) {
  if (!c) return '<button type="button" class="btn btn-flori btn-flori-sm" data-reativar="saude">Aceitar</button>';
  if (!c.aceito) return '<button type="button" class="btn btn-flori btn-flori-sm" data-reativar="saude">Reativar</button>';
  if (revogando === 'saude') {
    return `<button type="button" class="btn btn-flori btn-flori-sm" data-confirmar-revogar="saude">Confirmar revogação</button>
      <button type="button" class="btn btn-flori-outline btn-flori-sm" data-cancelar>Cancelar</button>`;
  }
  return '<button type="button" class="btn btn-flori-outline btn-flori-sm" data-revogar="saude">Revogar</button>';
}

function blocoSaude() {
  if (perfil.perfil === 'admin') return '';
  const c = perfil.consentimento_saude;
  let situacaoConsentimento = 'Ainda não aceito.';
  if (c && c.aceito) situacaoConsentimento = `Aceito em ${dataLonga(c.data)} (versão ${esc(c.versao_documento)})`;
  else if (c) situacaoConsentimento = `Revogado em ${dataLonga(c.data)}. Seus registros continuam guardados até você apagar.`;
  return `<section class="flori-card flori-perfil-bloco" aria-label="Meu ciclo e saúde">
      <h2 class="flori-heading">Meu ciclo e saúde</h2>
      <p class="flori-hint">Só você vê essas informações. A equipe do Flori não tem acesso a elas.</p>
      <div class="flori-saude-perfil">
        <div class="flori-consentimento">
          <strong>Você já menstrua?</strong>
          <small class="flori-hint">${esc(rotuloDaSituacao(perfil.situacao_menstrual))}</small>
          <div class="flori-consentimento-acoes">
            <button type="button" class="btn btn-flori-outline btn-flori-sm" id="botaoAlterarSituacao">Alterar</button>
          </div>
        </div>
        <div class="flori-consentimento">
          <strong>Consentimento de dados de saúde</strong>
          <small class="flori-hint">${situacaoConsentimento}</small>
          <div class="flori-consentimento-acoes">${acoesSaude(c)}</div>
        </div>
      </div>
      <button type="button" class="btn flori-btn-perigo-contorno btn-flori-sm mt-3" id="botaoApagarDiario">Apagar todo o meu diário</button>
      <div class="flori-success" id="sucessoSaude" role="status"></div>
      <div class="flori-error" id="erroSaude" role="alert"></div>
    </section>`;
}

async function alterarSituacao() {
  const estado = await perguntarSituacao({ temConsentimento: Boolean(perfil.consentimento_saude?.aceito), podeAdiar: false });
  if (estado) window.location.reload();
}

async function apagarDiario() {
  const sim = await confirmar({
    titulo: 'Apagar todo o seu diário?',
    texto: 'Todos os registros de menstruação, humor e sintomas serão apagados para sempre. Isso não pode ser desfeito.',
    rotulo: 'Apagar tudo', perigo: true,
  });
  if (!sim) return;
  try {
    const { ok, dados } = await chamarApi('/diario', { metodo: 'DELETE', corpo: { confirmar: true } });
    if (!ok) throw new Error(dados.mensagem);
    mostrar('sucessoSaude', 'Seu diário foi apagado.');
  } catch (erro) {
    mostrar('erroSaude', erro.message || 'Sem conexão com o servidor. Tente de novo.');
  }
}

function desenhar() {
  painel.innerHTML = `<div class="flori-perfil">
    <section class="flori-card flori-perfil-bloco" aria-label="Dados pessoais">
      <h2 class="flori-heading">Dados pessoais</h2>
      <form id="formPerfil" novalidate>
        <div class="row g-3">
          <div class="col-sm-6 col-lg-4"><label class="form-label" for="nome">Nome</label>
            <input type="text" class="form-control" id="nome" value="${esc(perfil.nome)}" autocomplete="given-name" required></div>
          <div class="col-sm-6 col-lg-4"><label class="form-label" for="sobrenome">Sobrenome</label>
            <input type="text" class="form-control" id="sobrenome" value="${esc(perfil.sobrenome)}" autocomplete="family-name" required></div>
          <div class="col-sm-6 col-lg-4"><label class="form-label" for="apelido">Como prefere ser chamada</label>
            <input type="text" class="form-control" id="apelido" value="${esc(perfil.apelido)}" autocomplete="nickname"></div>
          <div class="col-sm-6 col-lg-4"><label class="form-label" for="celular">Celular <span class="flori-hint">(opcional)</span></label>
            <input type="tel" class="form-control" id="celular" value="${esc(perfil.celular || '')}" placeholder="(11) 90000-0000" autocomplete="tel"></div>
          <div class="col-sm-6 col-lg-4"><label class="form-label" for="email">Email</label>
            <div class="flori-campo-acao">
              <input type="email" class="form-control" id="email" value="${esc(perfil.email || '')}" readonly>
              ${perfil.tem_senha ? '<button type="button" class="btn btn-flori-outline" id="botaoTrocarEmail">Trocar email</button>' : ''}
            </div>
            ${perfil.tem_senha ? '' : '<small class="flori-hint flori-campo-nota">O email desta conta vem do Google.</small>'}</div>
          <div class="col-sm-6 col-lg-4"><label class="form-label" for="nascimento">Nascimento</label>
            <input type="text" class="form-control" id="nascimento" value="${esc(perfil.data_nascimento)}" readonly>
            <small class="flori-hint flori-campo-nota">Só pode ser alterada por pedido ao canal de privacidade.</small></div>
        </div>
        <div class="flori-perfil-salvar">
          <button type="submit" class="btn btn-flori" id="botaoSalvar">Salvar alterações</button>
        </div>
        <div class="flori-error" id="erroPerfil" role="alert"></div>
        <div class="flori-success" id="sucessoPerfil" role="status"></div>
      </form>
    </section>
    <section class="flori-card flori-perfil-bloco" aria-label="Consentimentos">
      <h2 class="flori-heading">Seus consentimentos</h2>
      <p class="flori-hint">Ao revogar, o Flori deixa de tratar seus dados: a trilha e a página Minha evolução ficam bloqueadas até você reativar.</p>
      <div class="flori-consentimentos">${perfil.consentimentos.map(blocoConsentimento).join('')}</div>
      <div class="flori-error" id="erroConsentimento" role="alert"></div>
    </section>
    ${blocoSaude()}
    <section class="flori-card flori-perfil-bloco flori-exportar" aria-label="Seus dados">
      <div class="flori-exportar-linha">
        <div class="flori-exportar-texto">
          <h2 class="flori-heading">Seus dados</h2>
          <p class="flori-hint">Baixe um arquivo com tudo o que o Flori guarda sobre você: cadastro, consentimentos, progresso na trilha, quiz, certificado e histórico de atividade.</p>
        </div>
        <button type="button" class="btn btn-flori-outline" id="botaoExportar">Baixar meus dados</button>
      </div>
      <div class="flori-error" id="erroExportar" role="alert"></div>
    </section>
    ${perfil.perfil === 'admin' ? '' : zonaDePerigo()}
  </div>`;
}

function zonaDePerigo() {
  return `<section class="flori-card flori-perfil-bloco flori-perigo" aria-label="Excluir minha conta">
      <h2 class="flori-heading">Excluir minha conta</h2>
      <p>A exclusão é definitiva e não pode ser desfeita.</p>
      <div class="flori-perigo-colunas">
        <div>
          <p class="mb-1"><strong>O que é apagado:</strong></p>
          <ul class="flori-hint">
            <li>seu nome, apelido, email, celular, data de nascimento, foto e senha;</li>
            <li>suas sessões abertas, seu progresso na trilha, suas tentativas do quiz e seu certificado.</li>
          </ul>
        </div>
        <div>
          <p class="mb-1"><strong>O que permanece:</strong></p>
          <ul class="flori-hint">
            <li>um registro inativo da conta, sem dados pessoais, só com um identificador interno;</li>
            <li>o histórico dos consentimentos que você deu, ligado a esse identificador, para comprovar o que foi aceito;</li>
            <li>os registros de segurança e auditoria, que nunca são apagados e perdem o endereço IP depois de 365 dias.</li>
          </ul>
        </div>
      </div>
      <p class="flori-hint">Depois da exclusão, o mesmo email pode ser usado em um novo cadastro, sem ligação com esta conta.</p>
      <button type="button" class="btn btn-perigo" id="botaoExcluirConta">Excluir minha conta</button>
    </section>`;
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

async function exportar() {
  const botao = document.getElementById('botaoExportar');
  mostrar('erroExportar', '');
  botao.disabled = true;
  try {
    const { ok, dados } = await chamarApi('/perfil/exportacao');
    if (!ok) throw new Error(dados.mensagem || 'Não foi possível gerar o arquivo.');
    const arquivo = new Blob([JSON.stringify(dados, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(arquivo);
    link.download = `flori_meus_dados_${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (erro) {
    mostrar('erroExportar', erro.message || 'Sem conexão com o servidor. Tente de novo.');
  } finally {
    botao.disabled = false;
  }
}

const modal = document.getElementById('modalExcluirConta');
const formExcluir = document.getElementById('formExcluirConta');
let desafioExclusao = null;

function abrirModalExclusao() {
  desafioExclusao = null;
  formExcluir.reset();
  document.getElementById('blocoSenha').hidden = !perfil.tem_senha;
  document.getElementById('blocoCodigo').hidden = perfil.tem_senha;
  document.getElementById('campoCodigo').hidden = true;
  mostrar('erroExcluir', '');
  mostrar('avisoCodigo', '');
  modal.showModal();
}

async function enviarCodigoExclusao() {
  const botao = document.getElementById('botaoEnviarCodigo');
  mostrar('erroExcluir', '');
  botao.disabled = true;
  try {
    const { ok, dados } = await chamarApi('/perfil/conta/codigo', { metodo: 'POST' });
    if (!ok) throw new Error(dados.mensagem || 'Não foi possível enviar o código.');
    desafioExclusao = dados.desafio;
    document.getElementById('campoCodigo').hidden = false;
    mostrar('avisoCodigo', `Enviamos um código para ${dados.email_mascarado}. Ele vale por ${dados.validade_minutos} minutos.`);
  } catch (erro) {
    mostrar('erroExcluir', erro.message || 'Sem conexão com o servidor. Tente de novo.');
  } finally {
    botao.disabled = false;
  }
}

async function confirmarExclusao(evento) {
  evento.preventDefault();
  mostrar('erroExcluir', '');
  const confirmacao = document.getElementById('confirmacaoExcluir').value.trim();
  if (confirmacao !== 'EXCLUIR') { mostrar('erroExcluir', 'Digite EXCLUIR, em letras maiúsculas, para confirmar.'); return; }

  const corpo = { confirmacao };
  if (perfil.tem_senha) {
    corpo.senha = document.getElementById('senhaExcluir').value;
    if (!corpo.senha) { mostrar('erroExcluir', 'Digite sua senha atual.'); return; }
  } else {
    if (!desafioExclusao) { mostrar('erroExcluir', 'Peça o código por email antes de confirmar.'); return; }
    corpo.desafio = desafioExclusao;
    corpo.codigo = document.getElementById('codigoExcluir').value;
  }

  const botao = document.getElementById('botaoConfirmarExclusao');
  botao.disabled = true;
  try {
    const { ok, dados } = await chamarApi('/perfil/conta', { metodo: 'DELETE', corpo });
    if (!ok) throw new Error(dados.mensagem || 'Não foi possível excluir a conta.');
    modal.close();
    await finalizarSessao('index.html');
  } catch (erro) {
    mostrar('erroExcluir', erro.message || 'Sem conexão com o servidor. Tente de novo.');
    botao.disabled = false;
  }
}

const modalEmail = document.getElementById('modalTrocarEmail');
const formEmail = document.getElementById('formTrocarEmail');
const formCodigoEmail = document.getElementById('formCodigoEmail');

function abrirTrocaEmail() {
  formEmail.reset();
  formCodigoEmail.reset();
  formEmail.hidden = false;
  formCodigoEmail.hidden = true;
  ['erroTrocaEmail', 'avisoTrocaEmail', 'erroCodigoEmail'].forEach((id) => mostrar(id, ''));
  modalEmail.showModal();
}

async function pedirCodigoEmail(evento) {
  evento.preventDefault();
  mostrar('erroTrocaEmail', '');
  const corpo = {
    email_novo: document.getElementById('emailNovo').value.trim(),
    senha: document.getElementById('senhaTrocaEmail').value,
  };
  if (!corpo.email_novo || !corpo.senha) { mostrar('erroTrocaEmail', 'Preencha o email novo e a senha atual.'); return; }

  const botao = document.getElementById('botaoPedirCodigoEmail');
  botao.disabled = true;
  try {
    const { ok, dados } = await chamarApi('/perfil/email', { metodo: 'POST', corpo });
    if (!ok) throw new Error(dados.mensagem || 'Não foi possível pedir a troca.');
    formEmail.hidden = true;
    formCodigoEmail.hidden = false;
    mostrar('avisoTrocaEmail', dados.mensagem);
    document.getElementById('codigoEmail').focus();
  } catch (erro) {
    mostrar('erroTrocaEmail', erro.message || 'Sem conexão com o servidor. Tente de novo.');
  } finally {
    botao.disabled = false;
  }
}

async function confirmarCodigoEmail(evento) {
  evento.preventDefault();
  mostrar('erroCodigoEmail', '');
  const codigo = document.getElementById('codigoEmail').value.replace(/\D/g, '');
  if (codigo.length !== 6) { mostrar('erroCodigoEmail', 'Digite os 6 números do código.'); return; }

  const botao = document.getElementById('botaoConfirmarEmail');
  botao.disabled = true;
  try {
    const { ok, status, dados } = await chamarApi('/perfil/email/confirmar', { metodo: 'POST', corpo: { codigo } });
    if (!ok) {
      if (status === 410 || status === 409) { formEmail.hidden = false; formCodigoEmail.hidden = true; mostrar('avisoTrocaEmail', ''); mostrar('erroTrocaEmail', dados.mensagem); return; }
      throw new Error(dados.mensagem || 'Não foi possível confirmar.');
    }
    perfil = dados;
    modalEmail.close();
    desenhar();
    mostrar('sucessoPerfil', 'Email alterado. As outras sessões abertas foram encerradas.');
  } catch (erro) {
    mostrar('erroCodigoEmail', erro.message || 'Sem conexão com o servidor. Tente de novo.');
  } finally {
    botao.disabled = false;
  }
}

formEmail.addEventListener('submit', pedirCodigoEmail);
formCodigoEmail.addEventListener('submit', confirmarCodigoEmail);
modalEmail.querySelectorAll('[data-fechar]').forEach((botao) => botao.addEventListener('click', () => modalEmail.close()));

formExcluir.addEventListener('submit', confirmarExclusao);
document.getElementById('botaoEnviarCodigo').addEventListener('click', enviarCodigoExclusao);
document.getElementById('cancelarExclusao').addEventListener('click', () => modal.close());
document.getElementById('fecharExclusao').addEventListener('click', () => modal.close());

painel.addEventListener('submit', (e) => { if (e.target.id === 'formPerfil') salvar(e); });

painel.addEventListener('click', (e) => {
  const alvo = (atributo) => e.target.closest(`[${atributo}]`);
  if (alvo('data-revogar')) { revogando = alvo('data-revogar').dataset.revogar; desenhar(); }
  else if (alvo('data-cancelar')) { revogando = null; desenhar(); }
  else if (alvo('data-confirmar-revogar')) alterarConsentimento(alvo('data-confirmar-revogar').dataset.confirmarRevogar, false);
  else if (alvo('data-reativar')) alterarConsentimento(alvo('data-reativar').dataset.reativar, true);
  else if (e.target.closest('#botaoExportar')) exportar();
  else if (e.target.closest('#botaoTrocarEmail')) abrirTrocaEmail();
  else if (e.target.closest('#botaoExcluirConta')) abrirModalExclusao();
  else if (e.target.closest('#botaoAlterarSituacao')) alterarSituacao();
  else if (e.target.closest('#botaoApagarDiario')) apagarDiario();
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
