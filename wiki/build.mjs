import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { marked } from 'marked';

const here = path.dirname(new URL(import.meta.url).pathname);
const root = path.resolve(here, '..');
const bookDir = path.join(root, 'book');
const chapterDir = path.join(bookDir, 'chapters');
const outDir = path.join(here, 'chapters');
const assetsDir = path.join(here, 'assets');
const diagramDir = path.join(assetsDir, 'diagrams');
fs.mkdirSync(outDir, { recursive: true });
execFileSync('python3', [path.join(here, 'render-diagrams.py')], { stdio: 'inherit' });
marked.setOptions({ gfm: true, breaks: false });

const summary = fs.readFileSync(path.join(bookDir, 'SUMMARY.md'), 'utf8');
const chapterMatches = [...summary.matchAll(/^\d+\. \[([^\]]+)\]\(chapters\/([^)]+)\)/gm)];
const appendixMatches = [...summary.matchAll(/^- \[([^\]]+)\]\(chapters\/([^)]+)\)/gm)];
const items = [...chapterMatches, ...appendixMatches].map((m, i) => ({
  title: m[1], file: m[2], slug: m[2].replace(/\.md$/, ''),
  label: i < chapterMatches.length ? String(i).padStart(2, '0') : String.fromCharCode(65 + i - chapterMatches.length),
  appendix: i >= chapterMatches.length,
}));
if (items.length !== 22) throw new Error(`Expected 22 chapters, found ${items.length}`);

const escapeHtml = (s) => s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const plain = (md) => md.replace(/<figure[\s\S]*?<\/figure>/g, ' ').replace(/\{\{diagram:[^}]+\}\}/g, ' ').replace(/```[\s\S]*?```/g, ' ')
  .replace(/`([^`]+)`/g, '$1').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
  .replace(/^#{1,6}\s+/gm, '').replace(/[>*_|]/g, ' ').replace(/\s+/g, ' ').trim();
const slugify = (s) => s.replace(/<[^>]+>/g, '').trim().toLowerCase()
  .replace(/[^\p{Letter}\p{Number}]+/gu, '-').replace(/^-|-$/g, '') || 'section';

function injectDiagrams(md) {
  return md.replace(/\{\{diagram:([a-z0-9-]+)\|([^}]+)\}\}/g, (_, name, caption) => {
    const file = path.join(diagramDir, `${name}.svg`);
    if (!fs.existsSync(file)) throw new Error(`Missing diagram: ${name}`);
    return `<figure class="diagram" tabindex="0">${fs.readFileSync(file, 'utf8')}<figcaption>图：${escapeHtml(caption)}</figcaption></figure>`;
  });
}

function renderMarkdown(md) {
  let html = marked.parse(injectDiagrams(md));
  const ids = new Map();
  html = html.replace(/<h([23])>([\s\S]*?)<\/h\1>/g, (_, level, inside) => {
    const base = slugify(inside), n = ids.get(base) || 0; ids.set(base, n + 1);
    const id = n ? `${base}-${n + 1}` : base;
    return `<h${level} id="${id}">${inside}<a class="anchor" href="#${id}" aria-label="链接到本节">#</a></h${level}>`;
  });
  return html.replace(/<table>/g, '<div class="table-wrap" tabindex="0"><table>').replace(/<\/table>/g, '</table></div>');
}

const records = items.map((item) => {
  const md = fs.readFileSync(path.join(chapterDir, item.file), 'utf8');
  const bodyMd = md.replace(/^# .+\n/, '');
  const text = plain(bodyMd), html = renderMarkdown(bodyMd);
  const headings = [...html.matchAll(/<h2 id="([^"]+)">([\s\S]*?)<a class="anchor"/g)].map(m => ({id:m[1],title:m[2].replace(/<[^>]+>/g,'')}));
  return {...item, md, html, text, headings, href:`chapters/${item.slug}.html`};
});

function topbar(prefix='') { return `<div class="progress" aria-hidden="true"></div><a class="skip" href="#main">跳到正文</a>
<header class="topbar"><a class="brand" href="${prefix}index.html"><span class="brand-mark">GPU</span><span>AI Infra from Scratch</span></a><nav class="tools" aria-label="阅读工具"><a class="tool-button" href="${prefix}search.html" aria-label="搜索">搜索</a><button class="tool-button" data-font-down aria-label="减小字号">A−</button><button class="tool-button" data-font-up aria-label="增大字号">A+</button><button class="tool-button" data-theme>深色</button><button class="tool-button" data-menu-open aria-label="打开目录">目录</button></nav></header>`; }
function menu(prefix='') { return `<dialog class="menu-panel" data-menu-panel><div class="menu-head"><span>全书目录</span><button class="tool-button" data-menu-close>关闭</button></div><nav class="menu-list">${records.map(r=>`<a href="${prefix}${r.href}"><span>${r.label}</span>${escapeHtml(r.title)}</a>`).join('')}</nav></dialog>`; }
function shell({title,body,prefix='',chapter=false,extraScripts=''}) { return `<!doctype html><html lang="zh-CN" data-theme="auto"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="面向初学者的 AI Infra 源码导读"><title>${escapeHtml(title)} · AI Infra from Scratch</title><link rel="stylesheet" href="${prefix}assets/reader.css"></head><body data-chapter="${chapter}">${topbar(prefix)}${body}${menu(prefix)}<footer class="site-footer">正文、图解与实验全新编写 · 事实快照沿用 2026-09-22</footer><script src="${prefix}assets/reader.js"></script>${extraScripts}</body></html>`; }

for (let i=0;i<records.length;i++) {
  const r=records[i], prev=records[i-1], next=records[i+1];
  const rail=`<aside class="chapter-rail"><div class="rail-label">${r.appendix?'Appendix':`Chapter ${r.label}`}</div><div class="rail-title">${escapeHtml(r.title)}</div><ol>${r.headings.map(h=>`<li><a href="#${h.id}">${escapeHtml(h.title)}</a></li>`).join('')}</ol></aside>`;
  const nav=`<nav class="chapter-nav" aria-label="章节导航">${prev?`<a href="${prev.slug}.html"><small>上一章</small><strong>${escapeHtml(prev.title)}</strong></a>`:''}${next?`<a class="next" href="${next.slug}.html"><small>下一章</small><strong>${escapeHtml(next.title)}</strong></a>`:''}</nav>`;
  const body=`<main id="main" class="reader-layout">${rail}<article class="chapter"><header class="chapter-head"><div class="chapter-number">${r.appendix?`附录 ${r.label}`:`第 ${r.label} 章`}</div><h1>${escapeHtml(r.title)}</h1><div class="chapter-meta">源码快照 2026-09-22 · 约 ${Math.max(4,Math.ceil(r.text.length/500)*2)} 分钟</div></header><div class="prose">${r.html}</div>${nav}</article></main>`;
  fs.writeFileSync(path.join(outDir,`${r.slug}.html`),shell({title:r.title,body,prefix:'../',chapter:true}));
}

const descriptions={
'00-preface':'阅读路线、范围与验证方法','01-request-journey':'从 HTTP 到 GPU kernel 的完整路径','02-model-basics':'只学容量规划需要的模型知识','03-gpu-basics':'计算、带宽、显存与 Roofline','04-memory-accounting':'权重、KV、激活与训练状态','05-prefill-decode':'TTFT 与逐 token 生成','06-kv-cache':'分页 block、容量和前缀复用','07-continuous-batching':'iteration 级动态调度','08-loading-quantization':'冷启动、精度与低比特权重','09-parallelism':'DP、TP、PP、CP 与 EP','10-collectives':'AllReduce 到 AllToAll','11-training-loop':'Forward、Backward 与 Optimizer','12-distributed-training':'FSDP、ZeRO 与 3D 并行','13-data-checkpoint':'数据背压、分片保存与恢复','14-kubernetes-gpu':'Device Plugin、MIG 与资源合同','15-batch-scheduling':'Gang、队列、公平与拓扑','16-serving-cluster':'路由、副本、冷启动与扩缩容','17-observability':'TTFT、TPOT、SLO 与成本','18-failure-recovery':'首错、重试、隔离与调和','19-platform-design':'从需求到小型 AI 平台','appendix-glossary':'术语、公式、命令与故障速查','appendix-sources':'七个仓库与官方材料地图'};
const rows=records.map(r=>`<a class="chapter-row" href="${r.href}"><span class="chapter-no">${r.label}</span><span><h3>${escapeHtml(r.title)}</h3><p>${escapeHtml(descriptions[r.slug]||'')}</p></span><span class="arrow">→</span></a>`).join('');
const home=`<main id="main"><section class="hero"><div><p class="kicker">从容量到等待</p><h1>从一张 GPU<br><em>到生产集群</em></h1><p class="dek">为档案馆搭建问答与校对平台：计算每份状态的空间，定位每一段等待，再验证跨卡、调度和恢复的边界。</p></div><aside class="hero-aside"><strong>零硬件也能学</strong>19 张图解与离线实验，以明确的输入核算容量、分页和调度，不将教学轮次冒充硬件性能。<dl class="snapshot"><dt>来源仓库</dt><dd>7 个官方仓库</dd><dt>参考资料</dt><dd>25 份文档与论文</dd><dt>快照日期</dt><dd>2026-09-22</dd></dl></aside></section><section class="home-grid"><aside class="home-intro"><h2>20 章 + 2 附录</h2><p>章节层级保持不变，讲解、图形与案例全部重写。以单卡算例起步，逐步进入通信、作业与服务治理。</p><a href="chapters/00-preface.html">从第 0 章开始 →</a><br><a href="search.html">全文搜索 →</a></aside><div class="contents">${rows}</div></section></main>`;
fs.writeFileSync(path.join(here,'index.html'),shell({title:'目录',body:home}));

const searchIndex=records.map(r=>({number:r.label,title:r.title,href:r.href,text:r.text}));
fs.writeFileSync(path.join(assetsDir,'search-index.json'),JSON.stringify(searchIndex,null,2));
fs.writeFileSync(path.join(assetsDir,'search-index.js'),`window.BOOK_SEARCH=${JSON.stringify(searchIndex)};\n`);
const search=`<main id="main" class="search-page"><p class="kicker">全书搜索</p><h1>从一个指标，<br>找到整条数据路径。</h1><label for="search" class="skip">搜索全书</label><input id="search" class="search-input" type="search" autocomplete="off" placeholder="KV Cache / NCCL / OOM"><section id="results" aria-live="polite"><p class="search-hint">输入概念、指标或故障，例如 TTFT、显存、AllReduce。</p></section></main>`;
fs.writeFileSync(path.join(here,'search.html'),shell({title:'搜索',body:search,extraScripts:'<script src="assets/search-index.js"></script><script src="assets/search.js"></script>'}));
// A chapter fragment needs its own ID namespace in the combined volume.
function volumeHtml(record) {
  const prefix = record.slug + '--';
  return record.html.replace(/\bid="([^"]+)"/g, (_, id) => `id="${prefix}${id}"`)
    .replace(/href="#([^"]+)"/g, (_, id) => `href="#${prefix}${id}"`)
    .replace(/aria-labelledby="([^"]+)"/g, (_, ids) =>
      `aria-labelledby="${ids.split(/\s+/).map(id => prefix + id).join(' ')}"`);
}
const combined=records.map(r=>`<section class="book-section"><header class="chapter-head"><div class="chapter-number">${r.label}</div><h1>${escapeHtml(r.title)}</h1></header><div class="prose">${volumeHtml(r)}</div></section>`).join('');
fs.writeFileSync(path.join(here,'book.html'),shell({title:'离线合订本',body:`<main id="main" class="reader-layout"><div></div><article class="chapter">${combined}</article></main>`,chapter:true}));
console.log(`Built ${records.length} chapters, 19 diagrams, index, search, and book.html`);
