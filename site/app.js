/* etalon landing page. Everything drawn here comes from site/data.json, which
   site/build_data.py writes from real etalon runs: fields are the solver's DFT
   at one wavelength, animated as Re[F·exp(−iωt)]; the run log is what the run
   recorded; the validation curve is the M0 measurement. Nothing is random. */
"use strict";

const STUDIO_DEMO_URL = "https://etalon-demo.netlify.app/";

const TEXT = {
  en: {
    tagline: "GPU photonic FDTD · on your own machine · Python-native",
    openStudio: "Open the Studio demo →",
    report: "M0 validation report",
    langButton: "中文",
    description:
      "A photonic FDTD solver that runs on one local NVIDIA GPU, with an identical-result CPU fallback. Select an entry: the viewport replays a field the etalon solver computed.",
    result: "RESULT:",
    subject: "Simulation",
    keywords: "Keywords",
    params: "Run parameters",
    liveStream: "Run log · recorded",
    computedOn: "Computed by etalon {version} on {device}.",
    empty: "No entry loaded. Select an entry to replay its field.",
    emptyTitle: "No entry loaded",
    emptyAbstract: "The viewport is idle.",
    figCut: "FIG. {n}: |{c}| ALONG THE CENTRE LINE, NORMALISED",
    figDispersion: "FIG. {n}: PHASE VELOCITY / c — MEASURED (DOTS) VS YEE THEORY (LINES)",
    role: "2D TE · λ = {wl} µm · component {c}",
    roleValidation: "2D vacuum · 0° and 45° · Δ = 50 and 100 nm",
    scale: "Re[F·e^(−iωt)] · λ = {wl} µm",
    tickerTop: [
      "etalon", "photonic FDTD on one local GPU", "M0: 2D TE solver, NumPy + CUDA",
      "CUDA = NumPy bit for bit", "2.9 × 10⁹ cell-updates/s on RTX 4060 Ti",
      "CPML −91 dB", "dispersion within 1.3 × 10⁻⁴ of Yee theory", "your data never leaves your machine",
    ],
    tickerLeft: ["Yee lattice", "CPML", "running DFT", "courant 0.99", "float32"],
    tickerRight: ["Data node: your GPU", "No cloud", "No telemetry"],
    results: {
      "SIM-01": "The cylindrical wave spreads evenly outward and leaves through the PML without a visible echo.",
      "SIM-02": "Most of the light stays in the silicon core and travels along x; a little radiates into the oxide.",
      "SIM-03": "A sharp corner scatters strongly; that is why real devices use arc or Euler bends.",
      "SIM-04": "Light reflected by the layers interferes with the incoming wave in front of the mirror.",
      "VAL-M0": "Measured phase velocity matches the Yee relation within 1.3 × 10⁻⁴ (acceptance 5 × 10⁻³); CUDA and NumPy agree bit for bit.",
    },
  },
  zh: {
    tagline: "GPU 光子 FDTD · 在你自己的机器上运行 · 原生 Python",
    openStudio: "打开 Studio 演示 →",
    report: "M0 验证报告",
    langButton: "EN",
    description:
      "在一块本地 NVIDIA GPU 上运行的光子 FDTD 求解器，CPU 回退结果完全一致。选择一个条目，视窗会回放 etalon 求解器算出的场。",
    result: "结果：",
    subject: "仿真",
    keywords: "关键词",
    params: "运行参数",
    liveStream: "运行日志 · 已录制",
    computedOn: "由 etalon {version} 在 {device} 上计算。",
    empty: "未加载条目。选择一个条目来回放它的场。",
    emptyTitle: "未加载条目",
    emptyAbstract: "视窗空闲。",
    figCut: "图 {n}：中心线上的 |{c}|，已归一化",
    figDispersion: "图 {n}：相速度 / c —— 测量（点）与 Yee 理论（线）",
    role: "二维 TE · λ = {wl} µm · 分量 {c}",
    roleValidation: "二维真空 · 0° 与 45° · Δ = 50 和 100 nm",
    scale: "Re[F·e^(−iωt)] · λ = {wl} µm",
    tickerTop: [
      "etalon", "单块本地 GPU 上的光子 FDTD", "M0：二维 TE 求解器，NumPy + CUDA",
      "CUDA 与 NumPy 逐位一致", "RTX 4060 Ti 上 2.9 × 10⁹ 次网格更新/秒",
      "CPML −91 dB", "色散与 Yee 理论相差 1.3 × 10⁻⁴ 以内", "数据不离开你的机器",
    ],
    tickerLeft: ["Yee 网格", "CPML", "实时 DFT", "Courant 0.99", "float32"],
    tickerRight: ["数据节点：你的 GPU", "不上云", "无遥测"],
    results: {
      "SIM-01": "柱面波均匀向外传播，穿过 PML 离开，没有可见的回波。",
      "SIM-02": "大部分光留在硅芯中沿 x 传播，少量辐射进氧化层。",
      "SIM-03": "急转直角散射很强——这就是实际器件用圆弧弯或欧拉弯的原因。",
      "SIM-04": "被各层反射的光在镜前与入射波干涉。",
      "VAL-M0": "测得的相速度与 Yee 色散关系相差 1.3 × 10⁻⁴ 以内（验收要求 5 × 10⁻³）；CUDA 与 NumPy 逐位一致。",
    },
    entries: {
      "SIM-01": { name: "真空脉冲", title: "自由空间中的点源", abstract: "磁线源向二维真空辐射 1.55 µm 脉冲，边界处的 CPML 将其吸收。" },
      "SIM-02": { name: "条形波导", title: "氧化硅中的 500 nm 硅条", abstract: "0.5 µm 硅芯（n = 3.476）中的面内偶极子，周围是 SiO2（n = 1.444）：TE 导模沿 x 传播。" },
      "SIM-03": { name: "直角弯", title: "硅条形波导的 90° 拐角", abstract: "同样的硅条做一个急转直角：一部分光跟着拐弯，其余散射进氧化层。" },
      "SIM-04": { name: "布拉格反射镜", title: "氧化硅中的八层硅", abstract: "光源前方是周期 370 nm、厚 110 nm 的八层硅：大部分光被反射，并与自身干涉。" },
      "VAL-M0": { name: "M0 验证", title: "二维真空中的数值色散", abstract: "在 0° 和 45° 两个方向上，用两个探针测量相速度，并与 Yee 色散关系对比。" },
    },
  },
};

const VALIDATION_ENTRY = {
  id: "VAL-M0",
  name: "M0 validation",
  title: "Numerical dispersion in 2D vacuum",
  abstract: "Phase velocity measured between two probes along 0° and 45°, compared with the Yee dispersion relation.",
  keys: ["YEE", "DISPERSION", "VALIDATION", "CUDA = NUMPY"],
};

const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (sel) => document.querySelector(sel);
let lang = "en";
try {
  lang = localStorage.getItem("etalon-lang") || ((navigator.language || "").startsWith("zh") ? "zh" : "en");
} catch {
  lang = (navigator.language || "").startsWith("zh") ? "zh" : "en";
}
let DATA = null;
let entries = [];
let current = null;
let fieldFrame = null;

function t(key, vars = {}) {
  const value = TEXT[lang][key] ?? TEXT.en[key];
  return typeof value === "string" ? value.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "") : value;
}

function entryText(e, key) {
  return (lang === "zh" && TEXT.zh.entries[e.id]?.[key]) || e[key];
}

function decode(b64) {
  return Int8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
}

/* ---------- Static text ---------- */
function applyText() {
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => (node.textContent = t(node.dataset.i18n)));
  $("#lang-btn").textContent = t("langButton");
  $("#studio-link").href = STUDIO_DEMO_URL;
  for (const [name, key] of [["top", "tickerTop"], ["left", "tickerLeft"], ["right", "tickerRight"]]) {
    const text = t(key).join(" • ") + " •";
    document.querySelectorAll(`[data-ticker="${name}"] span`).forEach((s) => (s.textContent = text));
  }
}

/* ---------- Archive list ---------- */
function buildList() {
  const list = $("#archive-list");
  list.replaceChildren();
  entries.forEach((e, i) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "row";
    const d = document.createElement("span");
    d.textContent = e.date;
    const n = document.createElement("span");
    n.textContent = entryText(e, "name");
    btn.append(d, n);
    btn.addEventListener("click", () => select(i));
    if (i === current) btn.setAttribute("aria-current", "true");
    li.appendChild(btn);
    list.appendChild(li);
  });
}

function select(i) {
  current = i;
  document.querySelectorAll(".row").forEach((r, k) => {
    if (k === i) r.setAttribute("aria-current", "true");
    else r.removeAttribute("aria-current");
  });
  render(i === null ? null : entries[i]);
}

function fill(parent, items, className) {
  parent.replaceChildren();
  items.forEach((text) => {
    const s = document.createElement("span");
    s.className = className;
    s.textContent = text;
    parent.appendChild(s);
  });
}

function render(e) {
  if (!e) {
    $("#exp-id").textContent = "EXP_ID: —";
    $("#exp-date").textContent = "—";
    $("#exp-log").textContent = t("empty");
    $("#exp-title").textContent = t("emptyTitle");
    $("#exp-team").textContent = "";
    $("#exp-abstract").textContent = t("emptyAbstract");
    $("#subject-name").textContent = "—";
    $("#subject-role").textContent = "";
    $("#scale-note").textContent = "";
    fill($("#tag-cloud"), [], "tag");
    fill($("#knobs"), ["—", "—", "—"], "knob");
    $("#figure-caption").textContent = "FIG. —";
    clearCanvas($("#figure"));
    fieldFrame = null;
    clearCanvas($("#field"));
    return;
  }
  const sim = e.field;
  $("#exp-id").textContent = "EXP_ID: " + e.id;
  $("#exp-date").textContent = e.date;
  $("#exp-log").textContent = t("results")[e.id];
  $("#exp-title").textContent = entryText(e, "title");
  $("#exp-team").textContent = t("computedOn", { version: DATA.etalon_version, device: sim.device.replace(/^cuda:0 /, "") });
  $("#exp-abstract").textContent = entryText(e, "abstract");
  $("#subject-name").textContent = entryText(e, "name");
  $("#subject-role").textContent = e.validation
    ? t("roleValidation")
    : t("role", { wl: sim.wavelength_um.toFixed(2), c: sim.component });
  $("#scale-note").textContent = t("scale", { wl: sim.wavelength_um.toFixed(2) });
  fill($("#tag-cloud"), e.keys, "tag");
  const n = String(current + 1).padStart(2, "0");
  if (e.validation) {
    const v = DATA.validation;
    fill($("#knobs"), [
      `MAX |v/vYee − 1|: ${v.max_residual.toExponential(1)}`,
      `CPML: ${v.cpml_db[0]} dB / ${v.cpml_db[1]} dB`,
      "CUDA = NUMPY: BITWISE",
      "2.9 × 10⁹ CELL-UPDATES/S",
    ], "knob");
    $("#figure-caption").textContent = t("figDispersion", { n });
    drawDispersion();
  } else {
    const p = sim.params;
    fill($("#knobs"), [p.grid, p.dx, p.steps], "knob");
    $("#figure-caption").textContent = t("figCut", { n, c: sim.component });
    drawCut(sim.cut);
  }
  startField(sim);
  startLog(sim.log);
}

/* ---------- Field: Re[F·exp(−iωt)] on the black void ---------- */
function startField(sim) {
  const [ny, nx] = sim.shape;
  const re = decode(sim.re);
  const im = decode(sim.im);
  const off = document.createElement("canvas");
  off.width = nx;
  off.height = ny;
  const offCtx = off.getContext("2d");
  const img = offCtx.createImageData(nx, ny);
  fieldFrame = { sim, re, im, nx, ny, off, offCtx, img, start: performance.now() };
  if (reduced) drawField(0);
}

function colour(v) {
  // diverging on black: positive warm (spectrum orange), negative cool (spectrum blue)
  const g = Math.pow(Math.min(1, Math.abs(v)), 0.55);
  return v >= 0 ? [255 * g, 127 * g, 20 * g] : [40 * g, 120 * g, 255 * g];
}

function drawField(phase) {
  const f = fieldFrame;
  if (!f) return;
  const c = Math.cos(phase);
  const s = Math.sin(phase);
  const d = f.img.data;
  for (let y = 0; y < f.ny; y++) {
    const row = (f.ny - 1 - y) * f.nx; // data rows run upward in y
    for (let x = 0; x < f.nx; x++) {
      const k = y * f.nx + x;
      const v = (f.re[k] * c + f.im[k] * s) / 127;
      const [r, g, b] = colour(v);
      const i = (row + x) * 4;
      d[i] = r;
      d[i + 1] = g;
      d[i + 2] = b;
      d[i + 3] = 255;
    }
  }
  f.offCtx.putImageData(f.img, 0, 0);

  const canvas = $("#field");
  const size = canvas.clientWidth * (window.devicePixelRatio || 1);
  if (canvas.width !== Math.round(size)) {
    canvas.width = Math.round(size);
    canvas.height = Math.round(size);
  }
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const scale = Math.min(canvas.width / f.nx, canvas.height / f.ny);
  const w = f.nx * scale;
  const h = f.ny * scale;
  const ox = (canvas.width - w) / 2;
  const oy = (canvas.height - h) / 2;
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(f.off, ox, oy, w, h);

  // structure outlines, in µm → canvas pixels
  const [x0, x1, y0, y1] = f.sim.extent_um;
  const px = (x) => ox + ((x - x0) / (x1 - x0)) * w;
  const py = (y) => oy + h - ((y - y0) / (y1 - y0)) * h;
  ctx.strokeStyle = "rgba(255,255,255,0.55)";
  ctx.lineWidth = Math.max(1, (window.devicePixelRatio || 1));
  ctx.save();
  ctx.beginPath();
  ctx.rect(ox, oy, w, h);
  ctx.clip();
  for (const [cx, cy, sx, sy] of f.sim.structures) {
    ctx.strokeRect(px(cx - sx / 2), py(cy + sy / 2), px(cx + sx / 2) - px(cx - sx / 2), py(cy - sy / 2) - py(cy + sy / 2));
  }
  ctx.restore();

  // reticle, as in the reference
  ctx.strokeStyle = "rgba(255,255,255,0.18)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(canvas.width / 2 + 0.5, 0);
  ctx.lineTo(canvas.width / 2 + 0.5, canvas.height);
  ctx.moveTo(0, canvas.height / 2 + 0.5);
  ctx.lineTo(canvas.width, canvas.height / 2 + 0.5);
  ctx.stroke();
}

function loop(now) {
  if (fieldFrame) drawField(((now - fieldFrame.start) / 2400) * 2 * Math.PI);
  requestAnimationFrame(loop);
}

function clearCanvas(canvas) {
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

/* ---------- Figure ---------- */
function axes(ctx, W, H) {
  ctx.strokeStyle = "rgba(255,255,255,0.45)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(30.5, 10);
  ctx.lineTo(30.5, H - 24.5);
  ctx.lineTo(W - 10, H - 24.5);
  ctx.stroke();
  ctx.fillStyle = "#fff";
  ctx.font = "10px 'JetBrains Mono', ui-monospace, monospace";
}

function drawCut(cut) {
  const c = $("#figure");
  const W = c.width;
  const H = c.height;
  const ctx = c.getContext("2d");
  clearCanvas(c);
  axes(ctx, W, H);
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 2;
  ctx.beginPath();
  cut.forEach((v, i) => {
    const x = 31 + (i / (cut.length - 1)) * (W - 42);
    const y = H - 25 - v * (H - 40);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.textAlign = "left";
  ctx.fillText("1", 12, 18);
  ctx.fillText("0", 12, H - 26);
  ctx.textAlign = "right";
  ctx.fillText("x →", W - 12, H - 8);
}

function drawDispersion() {
  const c = $("#figure");
  const W = c.width;
  const H = c.height;
  const ctx = c.getContext("2d");
  clearCanvas(c);
  axes(ctx, W, H);
  const curves = DATA.validation.dispersion;
  const all = Object.values(curves);
  const nMin = Math.min(...all.map((d) => d.cells_per_wavelength[0]));
  const nMax = Math.max(...all.map((d) => d.cells_per_wavelength.at(-1)));
  const vMin = Math.min(...all.flatMap((d) => d.theory)) - 0.0005;
  const vMax = 1.0005;
  const px = (n) => 31 + ((Math.log(n) - Math.log(nMin)) / (Math.log(nMax) - Math.log(nMin))) * (W - 45);
  const py = (v) => H - 25 - ((v - vMin) / (vMax - vMin)) * (H - 40);
  const colours = { 0: "#ff7f00", 45: "#5fa8ff" };
  for (const [angle, d] of Object.entries(curves)) {
    ctx.strokeStyle = colours[angle];
    ctx.lineWidth = 2;
    ctx.beginPath();
    d.cells_per_wavelength.forEach((n, i) => (i ? ctx.lineTo(px(n), py(d.theory[i])) : ctx.moveTo(px(n), py(d.theory[i]))));
    ctx.stroke();
    ctx.fillStyle = colours[angle];
    d.cells_per_wavelength.forEach((n, i) => {
      ctx.beginPath();
      ctx.arc(px(n), py(d.measured[i]), 3, 0, 2 * Math.PI);
      ctx.fill();
    });
  }
  ctx.strokeStyle = "rgba(255,255,255,0.35)";
  ctx.setLineDash([3, 3]);
  ctx.beginPath();
  ctx.moveTo(31, py(1));
  ctx.lineTo(W - 10, py(1));
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#fff";
  ctx.textAlign = "left";
  ctx.fillText("v/c = 1", 36, py(1) - 4);
  ctx.fillText("0°", px(nMin) + 4, py(curves["0"].theory[0]) - 6);
  ctx.fillText("45°", px(nMin) + 4, py(curves["45"].theory[0]) + 14);
  ctx.textAlign = "right";
  ctx.fillText("cells per wavelength →", W - 12, H - 8);
}

/* ---------- Run log ---------- */
let logTimer = null;
function startLog(log) {
  clearInterval(logTimer);
  const lines = [];
  let k = 0;
  const tick = () => {
    const [n, e, sec] = log[k % log.length];
    lines.unshift(`STEP ${String(n).padStart(5)} >> E/Emax ${e.toExponential(2)} · ${sec.toFixed(2)} s`);
    if (lines.length > 10) lines.length = 10;
    $("#live-data").textContent = lines.join("\n");
    k += 1;
  };
  tick();
  logTimer = setInterval(tick, reduced ? 900 : 180);
}

/* ---------- Boot ---------- */
function init(data) {
  DATA = data;
  const date = new Date(data.generated);
  const stamp = [date.getDate(), date.getMonth() + 1, date.getFullYear() % 100]
    .map((v) => String(v).padStart(2, "0"))
    .join(".");
  entries = data.cases.map((c) => ({ ...c, date: stamp, field: c }));
  entries.push({ ...VALIDATION_ENTRY, date: "15.10.26", field: data.cases[0], validation: true });
  applyText();
  buildList();
  select(0);
  requestAnimationFrame(loop);
}

$("#lang-btn").addEventListener("click", () => {
  lang = lang === "zh" ? "en" : "zh";
  try {
    localStorage.setItem("etalon-lang", lang);
  } catch {
    /* private mode: language just isn't remembered */
  }
  applyText();
  buildList();
  render(current === null ? null : entries[current]);
});
$("#close-btn").addEventListener("click", () => select(null));

applyText();
fetch("data.json")
  .then((r) => r.json())
  .then(init)
  .catch(() => {
    $("#exp-log").textContent = "data.json could not be loaded.";
  });
