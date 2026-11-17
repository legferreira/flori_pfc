import { test } from 'node:test';
import assert from 'node:assert/strict';

import { paginasDoMenu } from '../js/compartilhado/navegacao.js';
import { abrirDiario, estadoDoDiario, TEXTOS_BLOQUEIO } from '../js/compartilhado/estado-diario.js';

const SITUACOES = [
  [null, false],
  ['ainda_nao', false],
  ['ja_menstruo', true],
  ['nao_tenho_certeza', true],
];

function user(situacao, disponivel) {
  return { perfil: 'user', situacao_menstrual: situacao, diario_disponivel: disponivel };
}

function idsDoMenu(perfil) {
  return paginasDoMenu(perfil).map((p) => p.id);
}

test('menu mostra o diário para user nas quatro situações', () => {
  for (const [situacao, disponivel] of SITUACOES) {
    assert.ok(idsDoMenu(user(situacao, disponivel)).includes('diario'), String(situacao));
  }
});

test('menu não mostra o diário para admin nem antes de saber o perfil', () => {
  assert.deepEqual(idsDoMenu({ perfil: 'admin', diario_disponivel: false }), ['admin', 'trilha']);
  assert.ok(!idsDoMenu(null).includes('diario'));
  assert.ok(!idsDoMenu({ apelido: 'Bia' }).includes('diario'));
});

function abrirComApiFalsa(perfil) {
  const chamadas = [];
  const chamarApi = (caminho) => { chamadas.push(caminho); return Promise.resolve({ ok: true, dados: {} }); };
  const telas = [];
  const estado = abrirDiario(perfil, {
    carregarDiario: () => { chamarApi('/diario/situacao'); chamarApi('/diario/resumo'); chamarApi('/diario?mes=2026-11'); },
    mostrarBloqueio: (caso) => telas.push(caso),
    mostrarAdmin: () => telas.push('admin'),
  });
  return { estado, chamadas, telas };
}

test('diário bloqueado não chama as APIs do diário e mostra o texto certo', () => {
  for (const [situacao, caso] of [[null, 'responder'], [undefined, 'responder'], ['ainda_nao', 'alterar']]) {
    const { estado, chamadas, telas } = abrirComApiFalsa(user(situacao, false));
    assert.equal(estado, caso);
    assert.deepEqual(chamadas, []);
    assert.deepEqual(telas, [caso]);
  }
  assert.equal(TEXTOS_BLOQUEIO.responder.texto, 'Para usar o Diário do corpo, conte para a gente: você já menstrua?');
  assert.equal(TEXTOS_BLOQUEIO.responder.botao, 'Responder agora');
  assert.equal(
    TEXTOS_BLOQUEIO.alterar.texto,
    'O Diário do corpo é para quem já menstrua ou não tem certeza. Quando isso mudar, é só alterar a sua resposta aqui.',
  );
  assert.equal(TEXTOS_BLOQUEIO.alterar.botao, 'Alterar minha resposta');
});

test('diário liberado carrega normalmente e admin não carrega', () => {
  for (const situacao of ['ja_menstruo', 'nao_tenho_certeza']) {
    const { estado, chamadas } = abrirComApiFalsa(user(situacao, true));
    assert.equal(estado, 'liberado');
    assert.ok(chamadas.includes('/diario/situacao'));
  }
  const admin = abrirComApiFalsa({ perfil: 'admin', diario_disponivel: false });
  assert.deepEqual(admin.chamadas, []);
  assert.deepEqual(admin.telas, ['admin']);
});

test('depois de responder, o novo estado decide a tela', () => {
  const perfil = user(null, false);
  assert.equal(estadoDoDiario(perfil), 'responder');
  Object.assign(perfil, { situacao_menstrual: 'ja_menstruo', diario_disponivel: true });
  assert.equal(estadoDoDiario(perfil), 'liberado');
  Object.assign(perfil, { situacao_menstrual: 'ainda_nao', diario_disponivel: false });
  assert.equal(estadoDoDiario(perfil), 'alterar');
});
