export const PAGINAS = [
  { id: 'trilha', href: 'home.html', rotulo: 'Trilha', icone: '<circle cx="6" cy="18" r="2.5" stroke="currentColor" stroke-width="2"/><circle cx="18" cy="6" r="2.5" stroke="currentColor" stroke-width="2"/><path d="M8 17c5 0 3-5 8-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="1 4"/>' },
  { id: 'diario', href: 'diario.html', rotulo: 'Diário do corpo', icone: '<path d="M6 4h11a1 1 0 0 1 1 1v15H7a1 1 0 0 1-1-1V4z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M9 9h6M9 13h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' },
  { id: 'dashboard', href: 'dashboard.html', rotulo: 'Minha evolução', icone: '<path d="M5 20V11M12 20V5M19 20v-7" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/>' },
];

export const PAGINA_ADMIN = { ...PAGINAS.find((p) => p.id === 'dashboard'), id: 'admin', href: 'admin.html', rotulo: 'Dashboard' };

export function paginasDoMenu(perfil) {
  if (perfil?.perfil === 'admin') return [PAGINA_ADMIN, PAGINAS.find((p) => p.id === 'trilha')];
  if (perfil?.perfil === 'user') return PAGINAS;
  return PAGINAS.filter((p) => p.id !== 'diario');
}
