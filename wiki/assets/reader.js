(() => {
  const root = document.documentElement;
  const key = 'lc-lg-reader';
  const saved = JSON.parse(localStorage.getItem(key) || '{}');
  let state = saved;
  const clamp = (n) => Math.max(17, Math.min(27, n));
  const save = (patch) => {
    state = {...state, ...patch};
    localStorage.setItem(key, JSON.stringify(state));
  };

  let size = clamp(saved.size || 20);
  root.style.setProperty('--reader-size', size + 'px');

  document.querySelector('[data-font-down]')?.addEventListener('click', () => {
    size = clamp(size - 1); root.style.setProperty('--reader-size', size + 'px'); save({size});
  });
  document.querySelector('[data-font-up]')?.addEventListener('click', () => {
    size = clamp(size + 1); root.style.setProperty('--reader-size', size + 'px'); save({size});
  });

  const themeButton = document.querySelector('button[data-theme]');
  const applyTheme = (theme) => {
    root.dataset.theme = theme;
    if (themeButton) themeButton.textContent = theme === 'dark' ? '浅色' : '深色';
  };
  applyTheme(saved.theme || 'auto');
  themeButton?.addEventListener('click', () => {
    const current = root.dataset.theme;
    const next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next); save({theme: next});
  });

  const pageKey = location.pathname;
  if (document.body.dataset.chapter === 'true') {
    const restore = saved.page === pageKey ? Number(saved.y || 0) : 0;
    if (restore > 120 && !location.hash) requestAnimationFrame(() => scrollTo(0, restore));
    let timer;
    addEventListener('scroll', () => {
      clearTimeout(timer);
      timer = setTimeout(() => save({page: pageKey, y: Math.round(scrollY), title: document.title}), 180);
      const h = document.documentElement.scrollHeight - innerHeight;
      root.style.setProperty('--progress', h > 0 ? `${Math.min(100, scrollY / h * 100)}%` : '100%');
    }, {passive: true});
  }

  document.querySelectorAll('pre').forEach((pre) => {
    const button = document.createElement('button');
    button.className = 'copy'; button.type = 'button'; button.textContent = '复制';
    button.addEventListener('click', async () => {
      await navigator.clipboard.writeText(pre.querySelector('code')?.innerText || pre.innerText);
      button.textContent = '已复制'; setTimeout(() => button.textContent = '复制', 1200);
    });
    pre.append(button);
  });

  const menu = document.querySelector('[data-menu-panel]');
  document.querySelector('[data-menu-open]')?.addEventListener('click', () => menu?.showModal());
  document.querySelector('[data-menu-close]')?.addEventListener('click', () => menu?.close());
  menu?.addEventListener('click', (event) => { if (event.target === menu) menu.close(); });
})();
