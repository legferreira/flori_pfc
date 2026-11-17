export const TEXTOS_BLOQUEIO = {
  responder: {
    texto: 'Para usar o Diário do corpo, conte para a gente: você já menstrua?',
    botao: 'Responder agora',
  },
  alterar: {
    texto: 'O Diário do corpo é para quem já menstrua ou não tem certeza. Quando isso mudar, é só alterar a sua resposta aqui.',
    botao: 'Alterar minha resposta',
  },
};

export function casoDeBloqueio(situacao) {
  return situacao === 'ainda_nao' ? 'alterar' : 'responder';
}

export function estadoDoDiario(perfil) {
  if (!perfil) return null;
  if (perfil.perfil === 'admin') return 'admin';
  if (!perfil.perfil) return 'desconhecido';
  if (perfil.diario_disponivel) return 'liberado';
  return casoDeBloqueio(perfil.situacao_menstrual);
}

export function abrirDiario(perfil, { carregarDiario, mostrarBloqueio, mostrarAdmin }) {
  const estado = estadoDoDiario(perfil);
  if (estado === 'admin') mostrarAdmin();
  else if (estado === 'liberado' || estado === 'desconhecido') carregarDiario();
  else if (estado) mostrarBloqueio(estado);
  return estado;
}
