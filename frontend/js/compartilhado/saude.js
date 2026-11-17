import { chamarApi } from './area-logada.js';
import { el } from './dom.js';

export const SITUACOES = [
  ['ja_menstruo', 'Já menstruo'],
  ['ainda_nao', 'Ainda não'],
  ['nao_tenho_certeza', 'Não tenho certeza'],
];
export const CHAVE_ADIADA = 'flori_situacao_adiada';

export function rotuloDaSituacao(codigo) {
  return (SITUACOES.find(([c]) => c === codigo) || [null, 'Sem resposta'])[1];
}

function abrirDialogo(dialogo, focar) {
  document.body.append(dialogo);
  dialogo.addEventListener('close', () => dialogo.remove());
  dialogo.showModal();
  (focar || dialogo.querySelector('button'))?.focus();
}

export function confirmar({ titulo, texto, rotulo = 'Confirmar', perigo = false }) {
  return new Promise((resolver) => {
    let resposta = false;
    const cancelar = el('button', { type: 'button', class: 'btn btn-flori-outline', text: 'Cancelar', onclick: () => dialogo.close() });
    const dialogo = el('dialog', { class: 'flori-modal', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'confirmarTitulo' },
      el('h2', { class: 'flori-heading h4', id: 'confirmarTitulo', text: titulo }),
      el('p', { text: texto }),
      el('div', { class: 'flori-saude-acoes' },
        cancelar,
        el('button', {
          type: 'button', class: perigo ? 'btn btn-perigo' : 'btn btn-flori', text: rotulo,
          onclick: () => { resposta = true; dialogo.close(); },
        })));
    dialogo.addEventListener('close', () => resolver(resposta));
    abrirDialogo(dialogo, cancelar);
  });
}

export function pedirConsentimentoSaude() {
  return new Promise((resolver) => {
    let aceito = false;
    const erro = el('p', { class: 'flori-error', role: 'alert', hidden: true });
    const aceitar = el('button', { type: 'button', class: 'btn btn-flori', text: 'Aceitar e continuar' });
    const dialogo = el('dialog', {
      class: 'flori-modal flori-saude-modal', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'saudeTitulo',
    },
    el('h2', { class: 'flori-heading h4', id: 'saudeTitulo', text: 'Seus dados de saúde' }),
    el('p', { text: 'Para guardar o seu diário do corpo, o Flori precisa da sua permissão.' }),
    el('ul', { class: 'flori-saude-lista' },
      el('li', {}, el('strong', { text: 'Quais dados: ' }), 'se você já menstrua, os dias de menstruação, o humor e os sintomas que você marcar.'),
      el('li', {}, el('strong', { text: 'Para quê: ' }), 'acompanhar o seu ciclo e mostrar o resumo e a previsão.'),
      el('li', {}, el('strong', { text: 'Quem vê: ' }), 'só você. A equipe do Flori não vê esses dados.'),
      el('li', {}, el('strong', { text: 'Você decide: ' }), 'pode revogar e apagar tudo quando quiser, no seu perfil.'),
      el('li', {}, 'Se não aceitar, a trilha continua disponível normalmente.')),
    erro,
    el('div', { class: 'flori-saude-acoes' },
      el('button', { type: 'button', class: 'btn btn-flori-outline', text: 'Agora não', onclick: () => dialogo.close() }),
      aceitar));
    aceitar.addEventListener('click', async () => {
      aceitar.disabled = true;
      erro.hidden = true;
      try {
        const { ok, dados } = await chamarApi('/perfil/consentimentos', { metodo: 'POST', corpo: { tipo: 'saude', aceito: true } });
        if (!ok) throw new Error(dados.mensagem);
        aceito = true;
        dialogo.close();
      } catch (falha) {
        erro.textContent = falha.message || 'Não foi possível registrar agora. Tente de novo.';
        erro.hidden = false;
        aceitar.disabled = false;
      }
    });
    dialogo.addEventListener('close', () => resolver(aceito));
    abrirDialogo(dialogo, aceitar);
  });
}

async function gravarSituacao(situacao) {
  const { ok, dados } = await chamarApi('/diario/situacao', { metodo: 'PUT', corpo: { situacao } });
  if (!ok) throw new Error(dados.mensagem || 'Não foi possível salvar agora.');
  return dados;
}

export function perguntarSituacao({ temConsentimento, podeAdiar = true }) {
  return new Promise((resolver) => {
    let resultado = null;
    let aguardandoConsentimento = false;
    const erro = el('p', { class: 'flori-error', role: 'alert', hidden: true });
    const escolher = async (codigo) => {
      erro.hidden = true;
      if (!temConsentimento) {
        aguardandoConsentimento = true;
        dialogo.close();
        if (!(await pedirConsentimentoSaude())) {
          try { sessionStorage.setItem(CHAVE_ADIADA, '1'); } catch {}
          resolver(null);
          return;
        }
        try {
          resolver(await gravarSituacao(codigo));
        } catch {
          resolver(null);
        }
        return;
      }
      try {
        resultado = await gravarSituacao(codigo);
        dialogo.close();
      } catch (falha) {
        erro.textContent = falha.message;
        erro.hidden = false;
      }
    };
    const opcoes = SITUACOES.map(([codigo, rotulo]) => el('button', {
      type: 'button', class: 'btn btn-flori-outline flori-saude-opcao', text: rotulo, onclick: () => escolher(codigo),
    }));
    const dialogo = el('dialog', {
      class: 'flori-modal', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'situacaoTitulo',
    },
    el('h2', { class: 'flori-heading h4', id: 'situacaoTitulo', text: 'Você já menstrua?' }),
    el('p', { class: 'flori-hint', text: 'Assim o Flori sabe se mostra o diário do corpo para você. Você pode mudar isso quando quiser no perfil.' }),
    el('div', { class: 'flori-saude-opcoes' }, opcoes),
    erro,
    podeAdiar ? el('button', {
      type: 'button', class: 'flori-saude-depois', text: 'Responder depois',
      onclick: () => {
        try { sessionStorage.setItem(CHAVE_ADIADA, '1'); } catch {}
        dialogo.close();
      },
    }) : el('button', { type: 'button', class: 'flori-saude-depois', text: 'Cancelar', onclick: () => dialogo.close() }));
    dialogo.addEventListener('close', () => { if (!aguardandoConsentimento) resolver(resultado); });
    abrirDialogo(dialogo, opcoes[0]);
  });
}

export function situacaoAdiada() {
  try { return sessionStorage.getItem(CHAVE_ADIADA) === '1'; } catch { return false; }
}
