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
