document.querySelectorAll('dialog [data-fechar]').forEach((botao) => {
  botao.addEventListener('click', () => botao.closest('dialog').close());
});
