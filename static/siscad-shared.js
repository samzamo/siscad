/* ===== SISCAD - utilitário compartilhado de paginação client-side ===== */
// containerSelector: elemento que envolve os itens (ex.: 'table' ou '.resultado-lista')
// itemSelector: seletor dos itens dentro do container (ex.: 'tr.pg-row' ou '.alvo-item')
// pageSize: itens por página
// controlsSelector: elemento com os botões .pg-prev/.pg-next e span .pg-info
function paginarLista(containerSelector, itemSelector, pageSize, controlsSelector) {
  const container = document.querySelector(containerSelector);
  const controls = document.querySelector(controlsSelector);
  if (!container) return;

  const items = Array.from(container.querySelectorAll(itemSelector));
  if (items.length <= pageSize) {
    if (controls) controls.style.display = 'none';
    return;
  }

  let pagina = 1;
  const totalPaginas = Math.ceil(items.length / pageSize);

  function render() {
    items.forEach((item, idx) => {
      const noRange = idx >= (pagina - 1) * pageSize && idx < pagina * pageSize;
      item.style.display = noRange ? '' : 'none';
    });
    if (controls) {
      const info = controls.querySelector('.pg-info');
      const prev = controls.querySelector('.pg-prev');
      const next = controls.querySelector('.pg-next');
      if (info) info.textContent = `Página ${pagina} de ${totalPaginas}`;
      if (prev) prev.disabled = pagina === 1;
      if (next) next.disabled = pagina === totalPaginas;
    }
  }

  if (controls) {
    controls.style.display = 'flex';
    const prev = controls.querySelector('.pg-prev');
    const next = controls.querySelector('.pg-next');
    if (prev) prev.addEventListener('click', () => { if (pagina > 1) { pagina--; render(); } });
    if (next) next.addEventListener('click', () => { if (pagina < totalPaginas) { pagina++; render(); } });
  }

  render();
}
