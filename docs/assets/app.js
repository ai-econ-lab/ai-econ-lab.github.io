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
  // The top line is the CEILING (30 Sep 2026): whole-text plus the hand-read share of bare "AI".
  // The whole-text line ("an AI term named anywhere") is drawn thin between ceiling and floor.
  // Falls back to the whole-text line if a page carries no ceiling.
  const YRS = window.AIEL_TREND.years, N = window.AIEL_TREND.values;
  const CE = window.AIEL_TREND.ceiling, hasCeil = CE && CE.length === YRS.length;
  const V = hasCeil ? CE : N;
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
  // floor line (ads that ask for AI in the role itself) — same provisional logic, second colour
  const F = window.AIEL_TREND.floor;
  if (F && F.length === YRS.length){
    const col2 = CSS("--c2");
    let df = ""; for (let i=0;i<=s;i++){ const x=X(YRS[i]),y=Y(F[i]); df += (df?"L":"M")+x.toFixed(1)+" "+y.toFixed(1)+" "; }
    g += `<path d="${df}" fill="none" stroke="${col2}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
    g += `<path d="M${X(YRS[s]).toFixed(1)} ${Y(F[s]).toFixed(1)} L${X(YRS[YRS.length-1]).toFixed(1)} ${Y(F[F.length-1]).toFixed(1)}" fill="none" stroke="${col2}" stroke-width="2" stroke-dasharray="4 3" stroke-linecap="round"/>`;
    const fx = X(YRS[YRS.length-1]), fy = Y(F[F.length-1]);
    g += `<circle cx="${fx}" cy="${fy}" r="3.5" fill="${CSS('--paper')}" stroke="${col2}" stroke-width="2"/>`;
  }
  // whole-text line, thin and muted: a step inside the range, not a bound
  if (hasCeil){
    const cm = CSS("--muted");
    let dn = ""; for (let i=0;i<=s;i++){ const x=X(YRS[i]),y=Y(N[i]); dn += (dn?"L":"M")+x.toFixed(1)+" "+y.toFixed(1)+" "; }
    g += `<path d="${dn}" fill="none" stroke="${cm}" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>`;
    g += `<path d="M${X(YRS[s]).toFixed(1)} ${Y(N[s]).toFixed(1)} L${X(YRS[YRS.length-1]).toFixed(1)} ${Y(N[N.length-1]).toFixed(1)}" fill="none" stroke="${cm}" stroke-width="1.4" stroke-dasharray="4 3" stroke-linecap="round"/>`;
  }
  // endpoint
  const lx = X(YRS[YRS.length-1]), ly = Y(V[V.length-1]);
  g += `<circle cx="${lx}" cy="${ly}" r="4.5" fill="${CSS('--paper')}" stroke="${col}" stroke-width="2.4"/>`;
  g += `<text class="ax" x="${lx-2}" y="${ly-11}" text-anchor="end" style="fill:${col};font-family:var(--sans);font-size:12px;font-weight:700">${hasCeil ? "Ceiling (broadest measure) " : ""}${V[V.length-1].toFixed(2)}%</text>`;
  svg.innerHTML = g;
  // hover
  const NS = "http://www.w3.org/2000/svg";
  const hv = document.createElementNS(NS,"line"); hv.setAttribute("class","axln"); hv.setAttribute("y1",m.t);
  hv.setAttribute("y2",m.t+ph); hv.style.opacity=0; hv.style.stroke=CSS("--muted"); svg.appendChild(hv);
  const dot = document.createElementNS(NS,"circle"); dot.setAttribute("r",4.5); dot.setAttribute("fill",CSS("--paper"));
  dot.setAttribute("stroke",col); dot.setAttribute("stroke-width",2.4); dot.style.opacity=0; svg.appendChild(dot);
  // Second hover dot for the floor. The chart drew two lines but the tooltip only ever read the
  // whole-text series, so hovering reported the ceiling and silently hid the floor -- on a figure
  // whose entire point is the distance between them (Magnus, 4 Aug).
  const dotF = document.createElementNS(NS,"circle"); dotF.setAttribute("r",4);
  dotF.setAttribute("fill",CSS("--paper")); dotF.setAttribute("stroke",CSS("--c2"));
  dotF.setAttribute("stroke-width",2); dotF.style.opacity=0; svg.appendChild(dotF);
  const hasFloor = F && F.length === YRS.length;
  svg.onpointermove = ev => {
    const b = svg.getBoundingClientRect(), sx = (ev.clientX-b.left)/b.width*W;
    let bi=0, bd=1e9; YRS.forEach((yr,i)=>{ const dd=Math.abs(X(yr)-sx); if(dd<bd){bd=dd;bi=i;} });
    const xx=X(YRS[bi]), yy=Y(V[bi]); hv.setAttribute("x1",xx); hv.setAttribute("x2",xx); hv.style.opacity=.5;
    dot.setAttribute("cx",xx); dot.setAttribute("cy",yy); dot.style.opacity=1;
    const prov = bi>=provIdx-1 && bi===YRS.length-1 ? " <span style='color:var(--warn)'>· provisional</span>" : "";
    // Series names match the legend and the methods note: "names" is the whole-text measure,
    // "asks for" is the role-scoped floor. "Broad AI share" matched neither.
    let rows = hasCeil
      ? `<div class="r"><span>Ceiling (broadest measure)</span><b>${CE[bi].toFixed(2)}%</b></div>` +
        `<div class="r"><span>AI term named anywhere</span><b>${N[bi].toFixed(2)}%</b></div>`
      : `<div class="r"><span>AI term named anywhere</span><b>${N[bi].toFixed(2)}%</b></div>`;
    if (hasFloor){
      dotF.setAttribute("cx",xx); dotF.setAttribute("cy",Y(F[bi])); dotF.style.opacity=1;
      rows += `<div class="r"><span>Floor: asks for AI in the role</span><b>${F[bi].toFixed(2)}%</b></div>`;
    }
    showTip(`<b>${YRS[bi]}</b>${rows}${prov}`, ev.clientX, ev.clientY);
  };
  svg.onpointerleave = () => { hv.style.opacity=0; dot.style.opacity=0; dotF.style.opacity=0; hideTip(); };
};
window.drawTrend();

/* Monthly-chart hover — the server-rendered monthly SVG gets the same readout as the hero
   trend chart (Magnus, 4 Sep 2026). Geometry comes off the SVG's own data-attributes and the
   series from the #aiel-monthly JSON block, both rendered from the same dict in build.py, so
   nothing here can drift from what the chart draws. */
(function monthlyHover(){
  const svg = document.querySelector("svg.rankchart.monthly");
  const el = document.getElementById("aiel-monthly");
  if (!svg || !el) return;
  let D; try { D = JSON.parse(el.textContent); } catch (e) { return; }
  const n = D.m.length; if (n < 2) return;
  const g = svg.dataset, x0 = +g.x0, x1 = +g.x1, top = +g.top, bot = +g.bot, ymax = +g.ymax;
  const W = (svg.viewBox.baseVal && svg.viewBox.baseVal.width) || 640;
  const X = i => x0 + i / (n - 1) * (x1 - x0);
  const Y = v => bot - Math.min(v, ymax) / ymax * (bot - top);
  const MONTHS = ["January","February","March","April","May","June",
                  "July","August","September","October","November","December"];
  const label = m => { const p = m.split("-"); return MONTHS[+p[1] - 1] + " " + p[0]; };
  const NS = "http://www.w3.org/2000/svg";
  const hv = document.createElementNS(NS, "line");
  hv.setAttribute("y1", top); hv.setAttribute("y2", bot); hv.style.opacity = 0;
  svg.appendChild(hv);
  const mk = r => { const d = document.createElementNS(NS, "circle");
    d.setAttribute("r", r); d.style.opacity = 0; svg.appendChild(d); return d; };
  const dot = mk(4.5), dotF = mk(4);
  svg.onpointermove = ev => {
    const b = svg.getBoundingClientRect(), sx = (ev.clientX - b.left) / b.width * W;
    let i = Math.round((sx - x0) / (x1 - x0) * (n - 1));
    i = Math.max(0, Math.min(n - 1, i));
    const xx = X(i);
    /* colours re-read per move so the theme toggle never leaves stale strokes behind */
    hv.style.stroke = CSS("--muted");
    hv.setAttribute("x1", xx); hv.setAttribute("x2", xx); hv.style.opacity = .5;
    dot.setAttribute("cx", xx); dot.setAttribute("cy", Y(D.ceil_ma ? D.ceil_ma[i] : D.ai_ma[i]));
    dot.setAttribute("fill", CSS("--paper")); dot.setAttribute("stroke", CSS("--c1"));
    dot.setAttribute("stroke-width", 2.4); dot.style.opacity = 1;
    dotF.setAttribute("cx", xx); dotF.setAttribute("cy", Y(D.floor_ma[i]));
    dotF.setAttribute("fill", CSS("--paper")); dotF.setAttribute("stroke", CSS("--c2"));
    dotF.setAttribute("stroke-width", 2); dotF.style.opacity = 1;
    /* Row names match the chart legend verbatim, and the 12-month means come first because
       they are the lines the section says to read. */
    showTip(`<b>${label(D.m[i])}</b>` +
      (D.ceil_ma ? `<div class="r"><span>Ceiling (broadest measure), 12-month mean</span><b>${D.ceil_ma[i].toFixed(2)}%</b></div>` : "") +
      `<div class="r"><span>AI term named anywhere, 12-month mean</span><b>${D.ai_ma[i].toFixed(2)}%</b></div>` +
      `<div class="r"><span>Asks for it in the role (floor), 12-month mean</span><b>${D.floor_ma[i].toFixed(2)}%</b></div>` +
      `<div class="r"><span>Ceiling, single month, unsmoothed</span><b>${(D.ceil ? D.ceil[i] : D.ai[i]).toFixed(2)}%</b></div>` +
      `<div class="r"><span>Distinct advertisements</span><b>${D.ads[i].toLocaleString("en-GB")}</b></div>`,
      ev.clientX, ev.clientY);
  };
  svg.onpointerleave = () => { hv.style.opacity = 0; dot.style.opacity = 0; dotF.style.opacity = 0; hideTip(); };
})();

/* DAIOE occupation lookup: "how exposed is your job?"
   Data: /assets/daioe_occupations.json, built by scripts/build_daioe_occupations.py from the
   published DAIOE release. Two measures (generative AI by default, all AI on the switch) and two
   classifications (ISCO-08 in English, SSYK 2012 in Swedish). Ranks are computed here from the
   raw index values: within year and classification, ties share a midrank, so an occupation is
   "more exposed than p% of the other occupations". Deep links: ?job=isco-2512&ai=allapps#find */
(function occSearch(){
  const tool = $(".occtool"), input = $("#occsearch"); if (!tool || !input) return;
  const sugg = $("#occsugg"), result = $("#occresult"), def = $("#occdef"), chips = $("#occchips");
  const segs = [...tool.querySelectorAll(".occsegbtn")];
  const esc = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const OTHER = { genai: "allapps", allapps: "genai" };
  const SETNAME = { isco: "ISCO-08", ssyk: "SSYK 2012" };
  const EXAMPLES = [["isco","Economists"],["isco","Software developers"],["isco","Nursing professionals"],
    ["isco","Primary school teachers"],["isco","Accountants"],["isco","Roofers"],["ssyk","Grundskollärare"],["ssyk","Undersköterskor, mottagning"]];
  let D = null, M = "genai", current = null, list = [], active = -1;
  const cache = {};

  // ---- ranks -------------------------------------------------------------------------------
  const val = (o, m, yi) => o[m === "genai" ? 2 : 3][yi];
  function sorted(set, m, yi){ const k = set + m + yi;
    return cache[k] || (cache[k] = D.sets[set].occ.map(o => val(o, m, yi)).sort((a, b) => a - b)); }
  function lowerBound(a, v){ let lo = 0, hi = a.length; while (lo < hi){ const mid = (lo + hi) >> 1; if (a[mid] < v) lo = mid + 1; else hi = mid; } return lo; }
  function standing(o, set, m, yi){
    const a = sorted(set, m, yi), v = val(o, m, yi), n = a.length;
    const below = lowerBound(a, v), eq = lowerBound(a, v + 1e-12) - below;
    const pct = 100 * (below + (eq - 1) / 2) / (n - 1);            // share of the OTHER occupations
    return { pct, rank: n - below - eq + 1, n, v };
  }
  const band = p => p >= 80 ? "Very high" : p >= 60 ? "High" : p >= 40 ? "Middle" : p >= 20 ? "Low" : "Very low";
  const LAST = () => D.years.length - 1;
  const lc = s => s.charAt(0).toLowerCase() + s.slice(1);          // "Generative AI" -> "generative AI"
  const edge = x => x > 82 ? " r" : x < 18 ? " l" : "";             // keep pin labels inside the card

  // ---- search ------------------------------------------------------------------------------
  function index(){
    for (const set of ["isco", "ssyk"]) D.sets[set].occ.forEach(o => {
      o._set = set; o._n = norm(o[1]); o._w = o._n.split(/[^a-z0-9]+/).filter(Boolean); });
    D._alias = Object.entries(D.aliases).map(([k, cs]) => [norm(k), cs]);
  }
  function score(o, q, toks){
    let s = 0;
    if (/^\d{3,4}$/.test(q)) return o[0].startsWith(q) ? 50 : 0;
    if (o._set === "isco") for (const [k, cs] of D._alias)
      if (q.length >= 2 && (k.startsWith(q) || q === k || q.startsWith(k + " ")) && cs.includes(o[0])) s = Math.max(s, 60);
    let tokScore = 0;
    for (const t of toks){
      // Light stemming so singulars find plural titles in both languages: "sjuksköterska" finds
      // "sjuksköterskor", "accountant" finds "Accountants". Inner matches ("lärare" in
      // "Gymnasielärare") count, but less than a match at the start of a word.
      const stems = [t];
      if (t.length > 4 && t.endsWith("s")) stems.push(t.slice(0, -1));
      if (t.length >= 6) stems.push(t.slice(0, -1));
      if (t.length >= 8) stems.push(t.slice(0, -2));
      if (o._w.some(w => stems.some(s => w.startsWith(s)))) tokScore += 10;
      else if (t.length >= 3 && stems.some(s => o._n.includes(s))) tokScore += 6;
      else { tokScore = 0; break; }
    }
    s = Math.max(s, tokScore);
    if (!s) return 0;
    if (o._n.startsWith(q)) s += 5;
    return s - o[1].length / 200;
  }
  function matches(raw){
    const q = norm(raw).trim(); if (!q || !D) return [];
    const toks = q.split(/[^a-z0-9]+/).filter(Boolean);
    const all = [...D.sets.isco.occ, ...D.sets.ssyk.occ];
    return all.map(o => [score(o, q, toks), o]).filter(x => x[0] > 0)
      .sort((a, b) => b[0] - a[0]).slice(0, 8).map(x => x[1]);
  }
  function showSugg(){
    list = matches(input.value); active = -1;
    if (!list.length){
      sugg.innerHTML = input.value.trim().length > 1
        ? `<div class="occnone">No match. Try a broader word, e.g. <i>teacher</i>, <i>engineer</i> or <i>lärare</i>.</div>` : "";
      sugg.style.display = sugg.innerHTML ? "block" : "none"; input.setAttribute("aria-expanded", "false"); return; }
    const yi = LAST();
    sugg.innerHTML = list.map((o, i) => { const st = standing(o, o._set, M, yi);
      return `<div class="occopt" role="option" id="occo-${i}" data-i="${i}" aria-selected="false">
        <span class="occoptname">${esc(o[1])}</span>
        <span class="occopttag" title="${SETNAME[o._set]}">${o._set === "isco" ? "EN" : "SV"}</span>
        <span class="occoptpct tnum">${Math.round(st.pct)}%</span></div>`; }).join("");
    sugg.style.display = "block"; input.setAttribute("aria-expanded", "true");
  }
  function setActive(i){
    const opts = [...sugg.querySelectorAll(".occopt")]; if (!opts.length) return;
    active = (i + opts.length) % opts.length;
    opts.forEach((el, j) => el.setAttribute("aria-selected", j === active ? "true" : "false"));
    input.setAttribute("aria-activedescendant", opts[active].id); opts[active].scrollIntoView({ block: "nearest" });
  }
  function closeSugg(){ sugg.style.display = "none"; input.setAttribute("aria-expanded", "false"); input.removeAttribute("aria-activedescendant"); }
  function choose(o){ input.value = o[1]; closeSugg(); render(o, true);
    if (o._set === "isco" && window.beeHighlight) window.beeHighlight(o[1]); }

  // ---- measure switch ----------------------------------------------------------------------
  function setMeasure(m, rerender){
    M = m; tool.dataset.measure = m;
    segs.forEach(b => b.setAttribute("aria-checked", b.dataset.m === m ? "true" : "false"));
    if (D) def.textContent = D.measures[m].def;
    if (rerender && current) render(current, true);
    if (sugg.style.display === "block") showSugg();
  }
  segs.forEach(b => b.addEventListener("click", () => setMeasure(b.dataset.m, true)));
  tool.querySelector(".occseg").addEventListener("keydown", e => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft" || e.key === "ArrowDown" || e.key === "ArrowUp"){
      e.preventDefault(); const m = OTHER[M]; setMeasure(m, true); segs.find(b => b.dataset.m === m).focus(); } });

  // ---- result card -------------------------------------------------------------------------
  function trendSVG(o, set, m){
    const ys = D.years, dist = D.sets[set].dist[m], s = o[m === "genai" ? 2 : 3];
    // Size the viewBox to the card, so the labels keep their real size on a phone
    // instead of shrinking with a fixed 640-wide drawing.
    const W = Math.max(300, Math.min(640, (result.clientWidth || 640) - 44)), H = W < 420 ? 150 : 176;
    const L = 8, R = W < 420 ? 74 : 92, T = 12, B = 26;
    const top = Math.max(...dist.p90, ...s) * 1.06;
    const X = i => L + i * (W - L - R) / (ys.length - 1), Y = v => T + (1 - v / top) * (H - T - B);
    const line = a => a.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
    const area = line(dist.p90) + dist.p10.map((v, i) => [i, v]).reverse().map(([i, v]) => `L${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("") + "Z";
    const k = ys.length - 1, lab = lc(D.measures[m].label);
    const yTicks = (W < 420 ? [2012, 2018, 2024] : [2012, 2016, 2020, 2024]).filter(y => ys.includes(y))
      .map(y => `<text x="${X(ys.indexOf(y)).toFixed(1)}" y="${H - 6}" text-anchor="middle" class="occax">${y}</text>`).join("");
    const yo = Y(s[k]), ym = Y(dist.p50[k]); const sep = Math.abs(yo - ym) < 13 ? (yo < ym ? -7 : 7) : 0;
    return `<svg class="occtrendsvg" viewBox="0 0 ${W} ${H}" role="img"
      aria-label="${esc(o[1])}: DAIOE ${lab} index from ${ys[0]} to ${ys[k]}, against the median occupation and the middle 80 per cent of occupations">
      <path d="${area}" class="occband80"/>
      <path d="${line(dist.p50)}" class="occmed"/>
      <path d="${line(s)}" class="occline"/>
      <circle cx="${X(k)}" cy="${yo}" r="4.5" class="occdot"/>
      <text x="${X(k) + 9}" y="${(yo + sep + 4).toFixed(1)}" class="occlbl occlblme">This job</text>
      <text x="${X(k) + 9}" y="${(ym - sep + 4).toFixed(1)}" class="occlbl">Median job</text>
      ${yTicks}</svg>`;
  }
  function render(o, push){
    result.style.display = "block";                                  // measured by trendSVG
    current = o; const set = o._set, yi = LAST(), Y0 = D.years[0], Y1 = D.years[yi];
    const me = standing(o, set, M, yi), ot = standing(o, set, OTHER[M], yi), first = standing(o, set, M, 0);
    const mL = D.measures[M].label, oL = D.measures[OTHER[M]].label, p = me.pct, q = ot.pct, gap = q - p;
    const cmp = Math.abs(gap) < 5
      ? `<b>${oL}</b> places it about the same: more exposed than ${Math.round(q)}%.`
      : `<b>${oL}</b> places it ${gap > 0 ? "higher" : "lower"}: more exposed than ${Math.round(q)}%.` +
        (Math.abs(gap) >= 10 ? ` The two measures count different AI capabilities, and the abilities this job relies on match the generative ones ${(M === "genai") === (gap < 0) ? "more" : "less"} closely than AI's other application areas.` : "");
    const drift = Math.round(p) - Math.round(first.pct);
    const trendTxt = Math.abs(drift) < 3
      ? `Exposure has grown since ${Y0}, as it has for every occupation, but its position among them has held steady (${Math.round(first.pct)}% in ${Y0}, ${Math.round(p)}% in ${Y1}).`
      : `Exposure has grown since ${Y0} for every occupation, and this one has moved ${drift > 0 ? "up" : "down"} the ranking: more exposed than ${Math.round(first.pct)}% in ${Y0}, ${Math.round(p)}% in ${Y1}.`;
    const occs = D.sets[set].occ.slice().sort((a, b) => val(a, M, yi) - val(b, M, yi)), at = occs.indexOf(o);
    const near = [at + 2, at + 1, at - 1, at - 2].filter(i => i >= 0 && i < occs.length && i !== at).map(i => occs[i]);
    result.innerHTML = `
      <div class="occhead"><span class="occbadge">${esc(mL)}</span>
        <span class="occcode mono">${SETNAME[set]} ${esc(o[0])} · ${Y1}</span></div>
      <h3 class="occname">${esc(o[1])}</h3>
      <p class="occbig">More exposed to ${esc(lc(mL))} than
        <b class="tnum">${Math.round(p)}%</b> of the other ${me.n - 1} occupations
        <span class="occbandchip">${band(p)} exposure</span></p>
      <div class="occscale2" aria-hidden="true">
        ${[20, 40, 60, 80].map(x => `<span class="occtick" style="left:${x}%"></span>`).join("")}
        ${["Very low", "Low", "Middle", "High", "Very high"].map((t, i) => `<span class="occbandlab${band(p) === t ? " on" : ""}" style="left:${i * 20 + 10}%">${t}</span>`).join("")}
        <span class="occpin ghost${edge(q)}" style="left:${q}%"><span class="occpinlab">${esc(oL)} ${Math.round(q)}%</span></span>
        <span class="occpin me${edge(p)}" style="left:${p}%"><span class="occpinlab">${esc(mL)} ${Math.round(p)}%</span></span>
      </div>
      <p class="occsent">Rank ${me.rank} of ${me.n} (1 = most exposed). ${cmp}</p>
      <div class="occtrend"><p class="occsub">How exposure has grown, ${Y0} to ${Y1}</p>
        ${trendSVG(o, set, M)}
        <p class="occkey"><span class="k me"></span>This job <span class="k med"></span>Median job <span class="k band"></span>Middle 80% of jobs</p>
        <p class="occsent">${trendTxt}</p></div>
      ${near.length ? `<div class="occnear"><p class="occsub">Nearby in the ranking</p>
        ${near.map(n => `<button type="button" class="occchip" data-set="${set}" data-code="${esc(n[0])}">${esc(n[1])} <span class="tnum">${Math.round(standing(n, set, M, yi).pct)}%</span></button>`).join("")}</div>` : ""}
      <div class="occfoot"><span>Index value ${me.v.toFixed(M === "genai" ? 2 : 1)} (${esc(lc(mL))}, ${Y1}).
        The two measures use different units, so compare rankings, not index values.
        ${set === "ssyk" ? "Swedish (SSYK) and international (ISCO) occupations are ranked separately, and the two classifications draw their lines differently, so the same job can rank differently in each." : ""}</span>
        <button type="button" class="occcopy">Copy link to this result</button></div>`;
    result.style.display = "block";
    if (push) history.replaceState(null, "", `?job=${set}-${o[0]}&ai=${M}#find`);
  }
  let rz; window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => { if (current) render(current, false); }, 200); });
  result.addEventListener("click", e => {
    const c = e.target.closest(".occchip");
    if (c){ const o = D.sets[c.dataset.set].occ.find(x => x[0] === c.dataset.code); if (o) choose(o); return; }
    const b = e.target.closest(".occcopy");
    if (b && navigator.clipboard) navigator.clipboard.writeText(location.href).then(() => { b.textContent = "Link copied"; setTimeout(() => b.textContent = "Copy link to this result", 1800); });
  });

  // ---- wiring ------------------------------------------------------------------------------
  input.addEventListener("input", showSugg);
  input.addEventListener("focus", () => { if (input.value) showSugg(); });
  input.addEventListener("keydown", e => {
    if (e.key === "ArrowDown"){ e.preventDefault(); if (sugg.style.display !== "block") showSugg(); setActive(active + 1); }
    else if (e.key === "ArrowUp"){ e.preventDefault(); setActive(active - 1); }
    else if (e.key === "Enter"){ e.preventDefault(); const o = list[active >= 0 ? active : 0]; if (o) choose(o); }
    else if (e.key === "Escape") closeSugg();
  });
  sugg.addEventListener("mousedown", e => e.preventDefault());
  sugg.addEventListener("click", e => { const el = e.target.closest(".occopt"); if (el) choose(list[+el.dataset.i]); });
  document.addEventListener("click", e => { if (!e.target.closest(".occsearchbox")) closeSugg(); });
  chips.addEventListener("click", e => { const c = e.target.closest(".occchip"); if (!c) return;
    const o = D.sets[c.dataset.set].occ.find(x => x[0] === c.dataset.code); if (o) choose(o); });

  fetch("/assets/daioe_occupations.json?v=1.0.0-2024").then(r => r.json()).then(d => {
    D = d; index();
    chips.innerHTML = `<span class="occsub">Try</span>` + EXAMPLES.map(([s, t]) => {
      const o = D.sets[s].occ.find(x => x[1] === t);
      return o ? `<button type="button" class="occchip" data-set="${s}" data-code="${o[0]}">${esc(t)}</button>` : ""; }).join("");
    const P = new URLSearchParams(location.search), ai = P.get("ai"), job = (P.get("job") || "").split("-");
    setMeasure(ai === "allapps" ? "allapps" : "genai", false);
    if (job.length === 2 && D.sets[job[0]]){ const o = D.sets[job[0]].occ.find(x => x[0] === job[1]);
      if (o){ input.value = o[1]; render(o, false);
        requestAnimationFrame(() => tool.scrollIntoView({ block: "start", behavior: "auto" })); } }
  }).catch(() => { result.innerHTML = '<p class="occsent">Occupation data could not load.</p>'; result.style.display = "block"; });
})();

/* DAIOE beeswarm — every occupation placed by generative-AI exposure, with scroll steps */
(function beeswarm(){
  const svg = $("#beeswarm"); if (!svg) return;
  fetch("/assets/daioe_occupations.json?v=1.0.0-2024").then(r => r.json()).then(d => {
    // Generative AI, ISCO-08, latest year; percentile = midrank share of the other occupations,
    // the same convention as the lookup above.
    const yi = d.years.length - 1, raw = d.sets.isco.occ.map(r => r[2][yi]), n = raw.length;
    const occ = d.sets.isco.occ.map(r => { const v = r[2][yi];
      const below = raw.filter(x => x < v).length, eq = raw.filter(x => x === v).length;
      return { t: r[1], s: v, p: 100 * (below + (eq - 1) / 2) / (n - 1) }; });
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
        showTip(`<b>${o.t}</b><div class="r"><span>More exposed to generative AI than</span><b>${Math.round(o.p)}%</b></div><div class="r"><span>Index value</span><b>${o.s.toFixed(2)}</b></div>`, ev.clientX, ev.clientY);
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
        var scale = parseInt(btn.dataset.scale || "2", 10);   // 2 = docs; 4 = slides (Beamer/PowerPoint)
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
            download(pngUrl, url.split("/").pop().replace(".svg", scale > 2 ? "_slides.png" : ".png"));
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

/* Open every disclosure before printing, and close it again after.

   The Monitor puts the caveats that do not bear on a first reading behind <details class="note">,
   which is only defensible if they come back in full whenever the page is printed, saved as PDF or
   archived. The stylesheet has carried a @media print rule since long before this that sets
   display:block on the children of details.note, and on 13 Aug 2026 it was verified and does NOT
   work: a closed <details> hides its content through the UA's own slot behaviour, which display on
   the child cannot override in Chrome. The caveats were silently absent from every printed copy.

   Doing it in script is the version that holds across browsers and does not depend on
   ::details-content, which is very new. Elements opened here are marked so that only those are
   closed again, leaving anything the reader had opened themselves alone. */
(function () {
  var opened = [];
  addEventListener("beforeprint", function () {
    opened = [];
    document.querySelectorAll("details:not([open])").forEach(function (d) {
      d.open = true; opened.push(d);
    });
  });
  addEventListener("afterprint", function () {
    opened.forEach(function (d) { d.open = false; });
    opened = [];
  });
})();
