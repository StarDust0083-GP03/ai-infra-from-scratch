(() => {
  const root = document.documentElement;
  const key = 'ai-infra-reader';
  let saved = {};
  try { const value = JSON.parse(localStorage.getItem(key) || '{}'); if (value && typeof value === 'object') saved = value; } catch {}
  let state = saved;
  const clamp = (n) => Math.max(17, Math.min(27, n));
  const save = (patch) => {
    state = {...state, ...patch};
    try { localStorage.setItem(key, JSON.stringify(state)); } catch {}
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

/* Progressive reading controls; no network and no dependency on writable storage. */
(() => {
  const root = document.documentElement;
  const themeKey = 'ebook-reader:appearance';
  const get = key => { try { return localStorage.getItem(key); } catch { return null; } };
  const put = (key, value) => { try { localStorage.setItem(key, value); } catch {} };
  let theme = get(themeKey) || root.dataset.theme || 'auto';
  if (!['auto', 'light', 'dark'].includes(theme)) theme = 'auto';
  const old = document.querySelector('button[data-theme]');
  const button = old ? old.cloneNode(true) : document.createElement('button');
  button.type = 'button';
  button.dataset.readerTheme = '';
  button.classList.add('control');
  if (old) old.replaceWith(button);
  else {
    const tools = document.querySelector('.reader-tools,.topbar .tools,.topbar,.bar-inner nav,.tools');
    if (tools) tools.append(button);
  }
  function applyTheme() {
    root.dataset.theme = theme;
    button.textContent = {auto:'自动',light:'浅色',dark:'深色'}[theme];
    button.setAttribute('aria-label', '外观：' + button.textContent + '，点击切换');
    button.title = '依次切换自动、浅色、深色';
  }
  applyTheme();
  button.addEventListener('click', () => {
    theme = {auto:'light',light:'dark',dark:'auto'}[theme];
    applyTheme(); put(themeKey, theme);
  });

  const bookNav = document.querySelector('.layout>nav.toc');
  if (bookNav) {
    const wrapper = document.createElement('details');
    wrapper.className = 'reader-book-toc';
    const wide = matchMedia('(min-width:1001px)');
    wrapper.open = wide.matches;
    wide.addEventListener('change', event => { wrapper.open = event.matches; });
    const summary = document.createElement('summary'); summary.textContent = '全书目录';
    bookNav.before(wrapper); wrapper.append(summary, bookNav);
  }
  const rail = document.querySelector('.chapter-rail');
  if (rail && !document.querySelector('.reader-mobile-toc')) {
    const list = rail.querySelector('ol');
    const header = document.querySelector('.chapter-head');
    if (list && header) {
      const toc = document.createElement('details');
      toc.className = 'reader-mobile-toc';
      const label = document.createElement('summary');
      label.textContent = '本章目录';
      toc.append(label, list.cloneNode(true));
      header.after(toc);
    }
  }
  document.querySelectorAll('table').forEach(table => {
    if (table.closest('.table-wrap')) return;
    const wrap = document.createElement('div');
    wrap.className = 'table-wrap';
    table.before(wrap); wrap.append(table);
  });
  document.querySelectorAll('.table-wrap').forEach(wrap => {
    wrap.tabIndex = 0;
    wrap.setAttribute('role', 'region');
    if (!wrap.hasAttribute('aria-label')) wrap.setAttribute('aria-label', '数据表，可横向滚动');
  });
  document.querySelectorAll('pre').forEach(pre => {
    pre.tabIndex = 0;
    pre.setAttribute('aria-label', '代码示例，可横向滚动');
  });
  document.querySelectorAll('.prose pre,.content pre').forEach(pre => {
    if (pre.querySelector('button')) return;
    const copy = document.createElement('button');
    copy.className = 'copy'; copy.type = 'button'; copy.textContent = '复制';
    pre.append(copy);
  });
  document.querySelectorAll('button.copy').forEach(oldButton => {
    // Replace the original listener so clipboard rejection always has a recovery.
    const copy = oldButton.cloneNode(true);
    oldButton.replaceWith(copy);
    copy.setAttribute('aria-label', '复制这段代码');
    copy.setAttribute('aria-live', 'polite');
    copy.addEventListener('click', async () => {
      const code = copy.closest('pre')?.querySelector('code');
      if (!code) return;
      try {
        await navigator.clipboard.writeText(code.textContent);
        copy.textContent = '已复制';
      } catch {
        const range = document.createRange(); range.selectNodeContents(code);
        const selection = getSelection(); selection.removeAllRanges(); selection.addRange(range);
        copy.textContent = '已选中';
        copy.title = '浏览器限制复制，请按 Ctrl+C 或长按复制';
      }
      setTimeout(() => { copy.textContent = '复制'; }, 1600);
    });
  });
  // Print folded examples too, then restore the reader's disclosure state.
  let printDetails = [];
  addEventListener('beforeprint', () => {
    printDetails = [...new Set([...printDetails, ...document.querySelectorAll('main details:not([open])')])];
    printDetails.forEach(details => { details.open = true; });
  });
  addEventListener('afterprint', () => {
    printDetails.forEach(details => { details.open = false; });
    printDetails = [];
  });
  const links = [...document.querySelectorAll('.chapter-rail a[href^="#"],.reader-mobile-toc a[href^="#"],nav.toc>a[href^="#"]')];
  const headings = [...new Set(links.map(link => document.getElementById(decodeURIComponent(link.hash.slice(1)))).filter(Boolean))];
  if (headings.length && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) {
        links.forEach(link => {
          if (decodeURIComponent(link.hash.slice(1)) === entry.target.id) link.setAttribute('aria-current','location');
          else link.removeAttribute('aria-current');
        });
      }
    }, {rootMargin:'-10% 0px -65% 0px'});
    headings.forEach(heading => observer.observe(heading));
  }
})();
