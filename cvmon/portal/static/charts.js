/* Gráficas SVG sin dependencias externas. Las zonas se distinguen por color Y forma. */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const COLORS = { accepted: "#1b6e2d", doubt: "#b86200", low: "#c62828", none: "#6b7580" };
  const W = 560, H = 260, M = { l: 44, r: 14, t: 28, b: 34 };

  function el(name, attrs, text) {
    const e = document.createElementNS(NS, name);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function frame(host, title, desc) {
    host.innerHTML = "";
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": title, width: "100%" });
    svg.appendChild(el("title", {}, title));
    svg.appendChild(el("desc", {}, desc));
    host.appendChild(svg);
    return svg;
  }
  function axes(svg, yMax, yLabel, ticks) {
    const x0 = M.l, x1 = W - M.r, y0 = H - M.b, y1 = M.t;
    svg.appendChild(el("line", { x1: x0, y1: y0, x2: x1, y2: y0, stroke: "#6b7580" }));
    svg.appendChild(el("line", { x1: x0, y1: y0, x2: x0, y2: y1, stroke: "#6b7580" }));
    for (let i = 0; i <= ticks; i++) {
      const v = (yMax * i) / ticks, y = y0 - ((y0 - y1) * i) / ticks;
      svg.appendChild(el("line", { x1: x0, y1: y, x2: x1, y2: y, stroke: "#e3e8ee" }));
      svg.appendChild(el("text", { x: x0 - 6, y: y + 4, "text-anchor": "end" }, v.toFixed(yMax <= 1 ? 1 : 0)));
    }
    svg.appendChild(el("text", { x: 4, y: 12 }, yLabel));
  }
  function marker(zone, x, y) {
    const c = COLORS[zone] || COLORS.none;
    if (zone === "accepted") return el("circle", { cx: x, cy: y, r: 3.6, fill: c });
    if (zone === "doubt") return el("rect", { x: x - 3.4, y: y - 3.4, width: 6.8, height: 6.8, fill: c });
    if (zone === "low") return el("path", { d: `M${x},${y - 4.5} L${x + 4.2},${y + 3.5} L${x - 4.2},${y + 3.5} Z`, fill: c });
    return el("circle", { cx: x, cy: y, r: 3, fill: "none", stroke: c });
  }

  function timeline(host, data) {
    const ev = data.events.filter((e) => e.confidence !== null);
    const svg = frame(host, "Confianza por evento",
      `${ev.length} eventos con puntuación; umbral inferior ${data.thresholds.lower}, superior ${data.thresholds.upper}`);
    axes(svg, 1, "confianza", 5);
    if (!ev.length) { svg.appendChild(el("text", { x: W / 2, y: H / 2, "text-anchor": "middle" }, "Sin eventos con puntuación")); return; }
    const n = data.events.length, x = (i) => M.l + ((W - M.l - M.r) * i) / Math.max(1, n - 1), y = (v) => H - M.b - (H - M.b - M.t) * v;
    [["lower", "inferior"], ["upper", "superior"]].forEach(([k, nm]) => {
      svg.appendChild(el("line", { x1: M.l, x2: W - M.r, y1: y(data.thresholds[k]), y2: y(data.thresholds[k]), stroke: "#333", "stroke-dasharray": "5 4" }));
      svg.appendChild(el("text", { x: W - M.r - 2, y: y(data.thresholds[k]) - 3, "text-anchor": "end" }, `${nm} ${data.thresholds[k]}`));
    });
    if (data.reference) svg.appendChild(el("line", { x1: M.l, x2: W - M.r, y1: y(data.reference.mean), y2: y(data.reference.mean), stroke: "#0b4f8a", "stroke-dasharray": "2 3" }));
    if (data.reference) svg.appendChild(el("text", { x: M.l + 4, y: y(data.reference.mean) - 3, fill: "#0b4f8a" }, `media referencia ${data.reference.mean.toFixed(2)}`));
    let path = "";
    data.events.forEach((e, i) => { if (e.confidence !== null) path += (path ? "L" : "M") + x(i) + "," + y(e.confidence); });
    svg.appendChild(el("path", { d: path, fill: "none", stroke: "#9aa5b1", "stroke-width": 1 }));
    data.events.forEach((e, i) => { if (e.confidence !== null) { const m = marker(e.zone, x(i), y(e.confidence)); m.appendChild(el("title", {}, `${e.event_id}: ${e.confidence.toFixed(3)} (${e.zone})`)); svg.appendChild(m); } });
    const t0 = data.events[0].captured_epoch, t1 = data.events[n - 1].captured_epoch;
    data.alerts.forEach((a) => {
      const f = t1 > t0 ? (a.fired_epoch - t0) / (t1 - t0) : 0, xx = M.l + (W - M.l - M.r) * Math.min(1, Math.max(0, f));
      svg.appendChild(el("line", { x1: xx, x2: xx, y1: M.t, y2: H - M.b, stroke: "#7a0a0a", "stroke-width": 1.5 }));
      svg.appendChild(el("text", { x: xx + 3, y: M.t + 10, fill: "#7a0a0a" }, a.rule_id));
    });
    svg.appendChild(el("text", { x: W / 2, y: H - 8, "text-anchor": "middle" }, "evento (orden temporal)"));
  }

  function zones(host, data) {
    const cnt = { accepted: 0, doubt: 0, low: 0, sin_puntuacion: 0 };
    data.events.forEach((e) => { cnt[e.zone || "sin_puntuacion"]++; });
    const total = data.events.length;
    const svg = frame(host, "Distribución por zona", `aceptada ${cnt.accepted}, duda ${cnt.doubt}, baja ${cnt.low}, sin puntuación ${cnt.sin_puntuacion}`);
    const rows = [["accepted", "Aceptada", cnt.accepted], ["doubt", "Duda", cnt.doubt], ["low", "Baja", cnt.low], ["none", "Sin puntuación", cnt.sin_puntuacion]];
    rows.forEach((r, i) => {
      const y = 30 + i * 52, w = total ? ((W - 190) * r[2]) / total : 0;
      svg.appendChild(el("text", { x: 8, y: y + 17 }, r[1]));
      svg.appendChild(el("rect", { x: 130, y: y, width: Math.max(w, 1), height: 28, fill: COLORS[r[0]] }));
      svg.appendChild(el("text", { x: 136 + w, y: y + 18 }, `${r[2]}${total ? " (" + ((100 * r[2]) / total).toFixed(0) + "%)" : ""}`));
    });
  }

  function histogram(host, data) {
    const confs = data.events.filter((e) => e.confidence !== null).map((e) => e.confidence), B = 10;
    const cur = new Array(B).fill(0);
    confs.forEach((c) => { cur[Math.min(B - 1, Math.floor(c * B))]++; });
    const props = cur.map((c) => (confs.length ? c / confs.length : 0)), ref = data.reference ? data.reference.hist_props : null;
    const svg = frame(host, "Distribución de confianza frente a la referencia",
      ref ? `run n=${confs.length}; referencia n=${data.reference.n}` : `run n=${confs.length}; sin referencia`);
    const ymax = Math.max(0.1, ...props, ...(ref || [0]));
    axes(svg, Math.ceil(ymax * 10) / 10, "proporción", 5);
    const ym = Math.ceil(ymax * 10) / 10, bw = (W - M.l - M.r) / B;
    for (let i = 0; i < B; i++) {
      const x = M.l + i * bw, hy = (p) => (H - M.b - M.t) * (p / ym);
      svg.appendChild(el("rect", { x: x + 3, y: H - M.b - hy(props[i]), width: bw / 2 - 3, height: hy(props[i]), fill: "#0b4f8a" }));
      if (ref) svg.appendChild(el("rect", { x: x + bw / 2, y: H - M.b - hy(ref[i]), width: bw / 2 - 3, height: hy(ref[i]), fill: "#9aa5b1" }));
      svg.appendChild(el("text", { x: x + bw / 2, y: H - 18, "text-anchor": "middle" }, (i / B).toFixed(1)));
    }
    svg.appendChild(el("text", { x: W - M.r, y: 12, "text-anchor": "end" }, ref ? "azul: run · gris: referencia" : "azul: run"));
  }

  function latency(host, data) {
    const ev = data.events.filter((e) => e.inference_ms !== null);
    const svg = frame(host, "Tiempo de inferencia por evento", `${ev.length} eventos`);
    if (!ev.length) { svg.appendChild(el("text", { x: W / 2, y: H / 2, "text-anchor": "middle" }, "Sin datos")); return; }
    const ymax = Math.ceil(Math.max(...ev.map((e) => e.inference_ms)) / 5) * 5 || 5;
    axes(svg, ymax, "ms", 5);
    const n = data.events.length, x = (i) => M.l + ((W - M.l - M.r) * i) / Math.max(1, n - 1), y = (v) => H - M.b - ((H - M.b - M.t) * v) / ymax;
    let p = ""; data.events.forEach((e, i) => { if (e.inference_ms !== null) p += (p ? "L" : "M") + x(i) + "," + y(e.inference_ms); });
    svg.appendChild(el("path", { d: p, fill: "none", stroke: "#0b4f8a", "stroke-width": 1.5 }));
    svg.appendChild(el("text", { x: W / 2, y: H - 8, "text-anchor": "middle" }, "evento (orden temporal)"));
  }

  async function init() {
    const root = document.getElementById("charts");
    if (!root) return;
    const run = root.dataset.run || "";
    let data;
    try {
      const r = await fetch("/api/series?run=" + encodeURIComponent(run));
      if (!r.ok) throw new Error(r.status);
      data = await r.json();
    } catch (e) {
      root.innerHTML = '<p class="empty" role="alert">No se pudieron cargar los datos de las gráficas.</p>';
      return;
    }
    if (!data.events.length) { root.innerHTML = '<p class="empty">Este run aún no tiene eventos para graficar.</p>'; return; }
    timeline(document.getElementById("ch-timeline"), data);
    zones(document.getElementById("ch-zones"), data);
    histogram(document.getElementById("ch-hist"), data);
    latency(document.getElementById("ch-latency"), data);
  }
  document.addEventListener("DOMContentLoaded", init);
})();
