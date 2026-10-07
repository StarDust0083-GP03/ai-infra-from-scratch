(() => {
  const input = document.querySelector('#search');
  const output = document.querySelector('#results');
  const index = window.BOOK_SEARCH || [];
  const esc = (s) => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const run = () => {
    const terms = input.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) { output.innerHTML = '<p class="search-hint">输入 API、概念或错误现象，例如 reducer、interrupt、重复副作用。</p>'; return; }
    const hits = index.map(item => {
      const hay = `${item.title} ${item.text}`.toLowerCase();
      const score = terms.reduce((n, t) => n + (hay.includes(t) ? (item.title.toLowerCase().includes(t) ? 4 : 1) : -100), 0);
      const first = Math.max(0, Math.min(...terms.map(t => hay.indexOf(t)).filter(n => n >= 0)) - 70);
      return {...item, score, excerpt: item.text.slice(first, first + 210)};
    }).filter(x => x.score >= terms.length).sort((a,b) => b.score - a.score).slice(0, 30);
    output.innerHTML = hits.length ? hits.map(x => `<article class="search-hit"><a href="${x.href}"><span>${esc(x.number)}</span><h2>${esc(x.title)}</h2><p>${esc(x.excerpt)}…</p></a></article>`).join('') : '<p class="search-hint">没有匹配结果。试试更短的关键词。</p>';
  };
  input.addEventListener('input', run);
  const q = new URLSearchParams(location.search).get('q'); if (q) { input.value = q; run(); }
  input.focus();
})();
