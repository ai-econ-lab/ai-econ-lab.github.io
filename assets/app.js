"use strict";
/* AI-Econ Lab — shared front-end: theme toggle + the monitor trend chart.
   Data is injected into window.AIEL_TREND by the page (from data/monitor.yaml). */
const $ = s => document.querySelector(s);
const CSS = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/* theme toggle — persists, and re-draws any chart on change */
(function themeInit(){
  const saved = localStorage.getItem("aiel-theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  const btn = $("#themebtn");
  if (btn) btn.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme")
      || (matchMedia("(prefers-color-scheme:dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("aiel-theme", next);
    if (window.drawTrend) window.drawTrend();
  });
  matchMedia("(prefers-color-scheme:dark)").addEventListener("change", () => {
    if (!document.documentElement.getAttribute("data-theme") && window.drawTrend) window.drawTrend();
  });
})();

/* tooltip */
const tip = $("#tip");
function showTip(html, x, y){
  if (!tip) return;
  tip.innerHTML = html; tip.style.opacity = 1;
  const r = tip.getBoundingClientRect();
  let px = x + 14, py = y + 14;
  if (px + r.width > innerWidth - 8) px = x - r.width - 14;
  if (py + r.height > innerHeight - 8) py = y - r.height - 14;
  tip.style.left = px + "px"; tip.style.top = py + "px";
}
const hideTip = () => { if (tip) tip.style.opacity = 0; };

/* the trend line — broad AI-in-demand share, with a dashed provisional final year */
window.drawTrend = function drawTrend(){
  const svg = $("#trend"); if (!svg || !window.AIEL_TREND) return;
  const YRS = window.AIEL_TREND.years, V = window.AIEL_TREND.values;
  const provIdx = window.AIEL_TREND.provisionalFrom;           // index where "provisional" begins
  const W = 640, H = 300, m = {l:44, r:58, t:16, b:34};
  const xmin = YRS[0], xmax = YRS[YRS.length-1], ymax = window.AIEL_TREND.ymax || 2.2;
  const pw = W-m.l-m.r, ph = H-m.t-m.b;
  const X = v => m.l + (v-xmin)/(xmax-xmin)*pw, Y = v => m.t + ph - (v/ymax)*ph;
  const col = CSS("--c1"); let g = "";
  (window.AIEL_TREND.yticks || [0,0.5,1,1.5,2]).forEach(t => { const y = Y(t);
    g += `<line class="gridln" x1="${m.l}" y1="${y}" x2="${W-m.r}" y2="${y}"/>`;
    g += `<text class="ax" x="${m.l-8}" y="${y+3}" text-anchor="end">${t}%</text>`; });
  YRS.forEach((yr,i) => { if (i%3 && i!==YRS.length-1) return;
    g += `<text class="ax" x="${X(yr)}" y="${H-m.b+17}" text-anchor="middle">${yr}</text>`; });
  g += `<line class="axln" x1="${m.l}" y1="${m.t+ph}" x2="${W-m.r}" y2="${m.t+ph}"/>`;
  // area under the solid segment
  const s = provIdx - 1;
  let da = `M${X(YRS[0]).toFixed(1)} ${Y(V[0]).toFixed(1)} `;
  for (let i=1;i<=s;i++) da += `L${X(YRS[i]).toFixed(1)} ${Y(V[i]).toFixed(1)} `;
  da += `L${X(YRS[s]).toFixed(1)} ${Y(0).toFixed(1)} L${X(YRS[0]).toFixed(1)} ${Y(0).toFixed(1)} Z`;
  g += `<path d="${da}" fill="var(--c1-soft)" stroke="none"/>`;
  // solid line to s
  let ds = ""; for (let i=0;i<=s;i++){ const x=X(YRS[i]),y=Y(V[i]); ds += (ds?"L":"M")+x.toFixed(1)+" "+y.toFixed(1)+" "; }
  g += `<path d="${ds}" fill="none" stroke="${col}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>`;
  // dashed provisional tail
  g += `<path d="M${X(YRS[s]).toFixed(1)} ${Y(V[s]).toFixed(1)} L${X(YRS[YRS.length-1]).toFixed(1)} ${Y(V[V.length-1]).toFixed(1)}" fill="none" stroke="${col}" stroke-width="2.4" stroke-dasharray="4 3" stroke-linecap="round"/>`;
  // endpoint
  const lx = X(YRS[YRS.length-1]), ly = Y(V[V.length-1]);
  g += `<circle cx="${lx}" cy="${ly}" r="4.5" fill="${CSS('--paper')}" stroke="${col}" stroke-width="2.4"/>`;
  g += `<text class="ax" x="${lx-2}" y="${ly-11}" text-anchor="end" style="fill:${col};font-family:var(--sans);font-size:12px;font-weight:700">${V[V.length-1].toFixed(2)}%</text>`;
  svg.innerHTML = g;
  // hover
  const NS = "http://www.w3.org/2000/svg";
  const hv = document.createElementNS(NS,"line"); hv.setAttribute("class","axln"); hv.setAttribute("y1",m.t);
  hv.setAttribute("y2",m.t+ph); hv.style.opacity=0; hv.style.stroke=CSS("--muted"); svg.appendChild(hv);
  const dot = document.createElementNS(NS,"circle"); dot.setAttribute("r",4.5); dot.setAttribute("fill",CSS("--paper"));
  dot.setAttribute("stroke",col); dot.setAttribute("stroke-width",2.4); dot.style.opacity=0; svg.appendChild(dot);
  svg.onpointermove = ev => {
    const b = svg.getBoundingClientRect(), sx = (ev.clientX-b.left)/b.width*W;
    let bi=0, bd=1e9; YRS.forEach((yr,i)=>{ const dd=Math.abs(X(yr)-sx); if(dd<bd){bd=dd;bi=i;} });
    const xx=X(YRS[bi]), yy=Y(V[bi]); hv.setAttribute("x1",xx); hv.setAttribute("x2",xx); hv.style.opacity=.5;
    dot.setAttribute("cx",xx); dot.setAttribute("cy",yy); dot.style.opacity=1;
    const prov = bi>=provIdx-1 && bi===YRS.length-1 ? " <span style='color:var(--warn)'>· provisional</span>" : "";
    showTip(`<b>${YRS[bi]}</b><div class="r"><span>Broad AI share</span><b>${V[bi].toFixed(3)}%</b></div>${prov}`, ev.clientX, ev.clientY);
  };
  svg.onpointerleave = () => { hv.style.opacity=0; dot.style.opacity=0; hideTip(); };
};
window.drawTrend();

/* DAIOE occupation lookup — "how exposed is your job?" (Die Zeit-style), sub-domain switchable */
(function occSearch(){
  const input = $("#occsearch"); if (!input) return;
  const sugg = $("#occsugg"), result = $("#occresult"), domSel = $("#occdom");
  let DATA = null, di = 0, current = null;
  fetch("/assets/daioe_occupations.json").then(r => r.json()).then(d => {
    DATA = d;
    domSel.innerHTML = d.domains.map((dm, i) => `<option value="${i}">${dm[1]}</option>`).join("");
    domSel.value = "0";
  }).catch(() => { result.innerHTML = '<p class="occsent">Occupation data could not load.</p>'; result.style.display = "block"; });
  const scoreOf = r => r[1 + di][0], pctlOf = r => r[1 + di][1];
  function render(row){
    current = row; const s = scoreOf(row), p = pctlOf(row);
    const rank = DATA.occ.filter(r => scoreOf(r) > s).length + 1, N = DATA.occ.length;
    const dl = DATA.domains[di][1];
    result.innerHTML = `<div class="occname">${row[0]}</div>
      <div class="occscore"><span class="tnum">${s.toFixed(2)}</span> <span class="occunit">${dl} exposure</span></div>
      <div class="occscale"><div class="occmark" style="left:${p}%"></div>
        <span class="occlab lo">less exposed</span><span class="occlab hi">more exposed</span></div>
      <p class="occsent">More exposed to ${dl} than <b>${Math.round(p)}%</b> of occupations
        (rank ${rank} of ${N}, ISCO-08 ${DATA.year}).</p>`;
    result.style.display = "block";
  }
  function matches(q){ q = q.toLowerCase().trim(); if (!q || !DATA) return [];
    return DATA.occ.filter(r => r[0].toLowerCase().includes(q)).sort((a, b) => scoreOf(b) - scoreOf(a)).slice(0, 7); }
  function showSugg(list){
    if (!list.length){ sugg.style.display = "none"; return; }
    sugg.innerHTML = list.map(r => `<button type="button" class="occopt" data-t="${r[0].replace(/"/g, "&quot;")}">${r[0]} <span class="tnum">${scoreOf(r).toFixed(2)}</span></button>`).join("");
    sugg.style.display = "block";
  }
  input.addEventListener("input", () => showSugg(matches(input.value)));
  input.addEventListener("focus", () => { if (input.value) showSugg(matches(input.value)); });
  input.addEventListener("keydown", e => { if (e.key === "Enter"){ const m = matches(input.value); if (m.length){ input.value = m[0][0]; sugg.style.display = "none"; render(m[0]); } } });
  sugg.addEventListener("click", e => { const b = e.target.closest(".occopt"); if (!b) return;
    const row = DATA.occ.find(r => r[0] === b.dataset.t); input.value = row[0]; sugg.style.display = "none"; render(row); });
  domSel.addEventListener("change", () => { di = +domSel.value; if (current) render(current); if (input.value) showSugg(matches(input.value)); });
  document.addEventListener("click", e => { if (!e.target.closest(".occsearchbox")) sugg.style.display = "none"; });
  input.addEventListener("keydown", e => { if (e.key === "Enter" && window.beeHighlight) { const m = matches(input.value); if (m.length) window.beeHighlight(m[0][0]); } });
  sugg.addEventListener("click", e => { const b = e.target.closest(".occopt"); if (b && window.beeHighlight) window.beeHighlight(b.dataset.t); });
})();

/* DAIOE beeswarm — every occupation placed by generative-AI exposure, with scroll steps */
(function beeswarm(){
  const svg = $("#beeswarm"); if (!svg) return;
  fetch("/assets/daioe_occupations.json").then(r => r.json()).then(d => {
    const occ = d.occ.map(r => ({ t: r[0], s: r[1][0], p: r[1][1] }));  // genAI = domain 0
    const W = 760, H = 340, pad = 28, r = 3.4, colW = 2 * r + 1.2, cy = H / 2;
    const ss = occ.map(o => o.s), smin = Math.min(...ss), smax = Math.max(...ss);
    const X = v => pad + (v - smin) / (smax - smin) * (W - 2 * pad);
    occ.sort((a, b) => a.s - b.s);
    const cols = {};
    occ.forEach(o => { const ci = Math.round(X(o.s) / colW); (cols[ci] = cols[ci] || []).push(o); o._x = ci * colW; });
    Object.values(cols).forEach(list => list.forEach((o, i) => { o._y = cy + (i % 2 ? 1 : -1) * Math.ceil(i / 2) * (2 * r + 1); }));
    const hx = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
    const lo = hx("--c2"), mid = hx("--c4"), hi = hx("--c1");
    const lerp = (a, b, t) => { a = a.replace("#",""); b = b.replace("#","");
      const ax = [0,2,4].map(i => parseInt(a.slice(i,i+2),16)), bx = [0,2,4].map(i => parseInt(b.slice(i,i+2),16));
      return "#" + ax.map((v,i) => Math.round(v + (bx[i]-v)*t).toString(16).padStart(2,"0")).join(""); };
    const colOf = p => p < 50 ? lerp(lo, mid, p/50) : lerp(mid, hi, (p-50)/50);
    svg.innerHTML = occ.map((o,i) => `<circle class="bee" data-i="${i}" cx="${o._x.toFixed(1)}" cy="${o._y.toFixed(1)}" r="${r}" fill="${colOf(o.p)}"/>`).join("");
    const circles = [...svg.querySelectorAll(".bee")];
    svg.addEventListener("pointermove", ev => { const t = ev.target;
      if (t.classList && t.classList.contains("bee")) { const o = occ[+t.dataset.i];
        showTip(`<b>${o.t}</b><div class="r"><span>genAI exposure</span><b>${o.s.toFixed(2)}</b></div><div class="r"><span>percentile</span><b>${Math.round(o.p)}</b></div>`, ev.clientX, ev.clientY);
      } else hideTip(); });
    svg.addEventListener("pointerleave", hideTip);
    function setHL(mode){ circles.forEach((c,i) => { const p = occ[i].p;
      const on = mode === "hi" ? p >= 88 : mode === "lo" ? p <= 12 : true;
      c.style.opacity = on ? 1 : 0.1; c.setAttribute("r", r); }); }
    const steps = document.querySelectorAll(".scrolly-steps .step");
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) {
      steps.forEach(s => s.classList.remove("active")); e.target.classList.add("active"); setHL(e.target.dataset.hl); } }),
      { rootMargin: "-45% 0px -45% 0px" });
    steps.forEach(s => io.observe(s));
    setHL("all");
    window.beeHighlight = name => { const idx = occ.findIndex(o => o.t === name);
      circles.forEach((c,i) => { c.style.opacity = idx < 0 ? 1 : (i === idx ? 1 : 0.1); c.setAttribute("r", i === idx ? 6 : r); }); };
  }).catch(() => {});
})();

/* Anti-spam e-mail: assemble the real address at runtime from data-attributes, so the
   static HTML only ever carries an obfuscated "(at)"/"(dot)" string for scrapers. */
(function () {
  document.querySelectorAll("a.email[data-u][data-d]").forEach(function (a) {
    var addr = a.getAttribute("data-u") + "@" + a.getAttribute("data-d");
    a.setAttribute("href", "mailto:" + addr);
    if (a.dataset.reveal !== "keep") a.textContent = addr;
  });
})();

/* Monitor lens toggle (gender etc.): swap which pre-rendered chart variant is shown. */
(function () {
  document.querySelectorAll(".lensmod").forEach(function (m) {
    m.querySelectorAll(".gbtn").forEach(function (b) {
      b.addEventListener("click", function () {
        var g = b.dataset.g;
        m.querySelectorAll(".gbtn").forEach(function (x) { x.classList.toggle("on", x === b); });
        m.querySelectorAll(".dumb").forEach(function (s) { s.classList.toggle("on", s.dataset.g === g); });
      });
    });
  });
})();

/* Monitor sticky sub-nav: pin it just below the sticky masthead, and highlight the
   module currently in view (scrollspy). Robust to the masthead's variable height. */
(function () {
  var nav = document.querySelector(".subnav");
  if (!nav) return;
  var mast = document.querySelector(".mast");
  function setOffset() {
    if (mast) document.documentElement.style.setProperty("--mast-h", mast.offsetHeight + "px");
  }
  setOffset();
  window.addEventListener("resize", setOffset);
  var links = Array.prototype.slice.call(nav.querySelectorAll("a"));
  var byId = {};
  links.forEach(function (a) { byId[a.dataset.spy] = a; });
  var secs = links.map(function (a) { return document.getElementById(a.dataset.spy); }).filter(Boolean);
  if (!secs.length) return;
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (e.isIntersecting) {
        links.forEach(function (x) { x.classList.remove("on"); });
        var a = byId[e.target.id];
        if (a) a.classList.add("on");
      }
    });
  }, { rootMargin: "-22% 0px -70% 0px" });
  secs.forEach(function (s) { io.observe(s); });
})();

/* Monitor Brief: 'Download PDF' = the browser's print-to-PDF of the print-styled sheet. */
(function () {
  var b = document.getElementById("printbrief");
  if (b) b.addEventListener("click", function () { window.print(); });
})();

/* Figure download: rasterise a static SVG to a PNG in the browser (no build dependency),
   so any figure can be dropped straight into a Word / Google / text document. */
(function () {
  function download(href, name) {
    var a = document.createElement("a");
    a.href = href; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  }
  document.querySelectorAll(".figpng").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var url = btn.dataset.svg;
      var label = btn.textContent; btn.textContent = "…";
      fetch(url).then(function (r) { return r.text(); }).then(function (svg) {
        var vb = (svg.match(/viewBox="([\d.\s-]+)"/) || [])[1];
        var w = 640, h = 300;
        if (vb) { var p = vb.trim().split(/\s+/).map(Number); w = p[2]; h = p[3]; }
        var scale = 2;                                   // crisp on-screen and in print
        var img = new Image();
        var blobUrl = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml;charset=utf-8" }));
        img.onload = function () {
          var c = document.createElement("canvas");
          c.width = w * scale; c.height = h * scale;
          var ctx = c.getContext("2d");
          ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, c.width, c.height);
          ctx.drawImage(img, 0, 0, c.width, c.height);
          URL.revokeObjectURL(blobUrl);
          c.toBlob(function (png) {
            var pngUrl = URL.createObjectURL(png);
            download(pngUrl, url.split("/").pop().replace(".svg", ".png"));
            setTimeout(function () { URL.revokeObjectURL(pngUrl); }, 1000);
            btn.textContent = label;
          }, "image/png");
        };
        img.onerror = function () { btn.textContent = label; };
        img.src = blobUrl;
      }).catch(function () { btn.textContent = label; });
    });
  });
})();
