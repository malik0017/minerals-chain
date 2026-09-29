/* Batch R2 — renders every <div data-mc-chart="ID"> with the ECharts option
   stored in <script type="application/json" id="ID">. Handles dark mode,
   RTL (Arabic) and resizing. Options are built server-side (partials/charts.html). */
(function () {
  var PALETTE = ["#0f766e", "#2563eb", "#d97706", "#dc2626", "#7c3aed", "#0891b2", "#65a30d", "#db2777", "#475569"];
  var charts = [];
  function isDark() {
    var t = document.documentElement.getAttribute("data-bs-theme") || document.body.getAttribute("data-bs-theme");
    return t === "dark";
  }
  function rtl() { return document.documentElement.getAttribute("dir") === "rtl"; }
  function fmt(v) {
    if (typeof v !== "number") return v;
    if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(1) + "K";
    return v.toLocaleString();
  }
  function prepare(opt) {
    opt.color = opt.color || PALETTE;
    opt.backgroundColor = "transparent";
    opt.textStyle = Object.assign({ fontFamily: "inherit" }, opt.textStyle || {});
    if (opt.tooltip === undefined) opt.tooltip = { trigger: "item" };
    var r = rtl();
    ["xAxis", "yAxis"].forEach(function (k) {
      var axes = opt[k]; if (!axes) return;
      (Array.isArray(axes) ? axes : [axes]).forEach(function (ax) {
        if (ax.type === "value") { ax.axisLabel = Object.assign({ formatter: fmt }, ax.axisLabel || {}); }
        if (r && k === "xAxis" && ax.type === "category") ax.inverse = true;
        if (r && k === "yAxis") ax.position = ax.position === "right" ? "left" : "right";
      });
    });
    if (r && opt.grid) { var g = opt.grid, l = g.left; g.left = g.right; g.right = l; }
    if (opt.legend && r) { opt.legend.left = opt.legend.left === "left" ? "right" : opt.legend.left; }
    return opt;
  }
  function renderAll() {
    if (!window.echarts) return;
    charts.forEach(function (c) { c.dispose(); }); charts = [];
    document.querySelectorAll("[data-mc-chart]").forEach(function (el) {
      var src = document.getElementById(el.getAttribute("data-mc-chart"));
      if (!src) return;
      var opt; try { opt = JSON.parse(src.textContent); } catch (e) { return; }
      var chart = echarts.init(el, isDark() ? "dark" : null, { renderer: "canvas" });
      chart.setOption(prepare(opt));
      var link = el.getAttribute("data-mc-link");
      if (link) chart.on("click", function (p) { if (p && p.data && p.data.key) window.location = link + encodeURIComponent(p.data.key); });
      charts.push(chart);
    });
  }
  window.addEventListener("resize", function () { charts.forEach(function (c) { c.resize(); }); });
  new MutationObserver(function (m) {
    if (m.some(function (x) { return x.attributeName === "data-bs-theme"; })) renderAll();
  }).observe(document.documentElement, { attributes: true });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", renderAll); else renderAll();
  window.McCharts = { render: renderAll };
})();
