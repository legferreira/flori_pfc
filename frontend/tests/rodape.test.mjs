import { test } from 'node:test';
import assert from 'node:assert/strict';

import { criarRodape, LINKS_DO_RODAPE } from '../js/compartilhado/rodape.js';
import { PAGINA_ADMIN, paginasDoMenu } from '../js/compartilhado/navegacao.js';

function documentoFalso() {
  return {
    createElement(tag) {
      return {
        tag,
        className: '',
        textContent: '',
        atributos: {},
        filhos: [],
        setAttribute(nome, valor) { this.atributos[nome] = valor; },
        append(...itens) { this.filhos.push(...itens); },
      };
    },
  };
}

test('rodapé gera os dois links legais abrindo em nova aba', () => {
  const rodape = criarRodape(documentoFalso());
  assert.equal(rodape.tag, 'footer');
  assert.equal(rodape.className, 'flori-rodape');
  const links = rodape.filhos.map((a) => ({ tag: a.tag, texto: a.textContent, ...a.atributos }));
  assert.deepEqual(links, [
    { tag: 'a', texto: 'Termos de uso', href: 'termos-de-uso.html', target: '_blank', rel: 'noopener' },
    { tag: 'a', texto: 'Política de privacidade', href: 'politica-privacidade.html', target: '_blank', rel: 'noopener' },
  ]);
  assert.equal(LINKS_DO_RODAPE.length, 2);
});

test('rodapé aceita classe extra sem perder a classe base', () => {
  assert.equal(criarRodape(documentoFalso(), { classeExtra: 'flori-rodape-logado' }).className, 'flori-rodape flori-rodape-logado');
});

test('menu do user chama a página de Minha evolução e o admin continua com Dashboard', () => {
  const user = paginasDoMenu({ perfil: 'user' });
  assert.equal(user.find((p) => p.id === 'dashboard').rotulo, 'Minha evolução');
  assert.ok(!user.some((p) => p.rotulo === 'Dashboard'));
  assert.equal(PAGINA_ADMIN.rotulo, 'Dashboard');
  assert.equal(PAGINA_ADMIN.href, 'admin.html');
});
