"use strict";

if (!localStorage.getItem("ecom_auth")) {
  location.replace("login.html");
}

var state = {
  meta: null,
  market: null,
  data: null,
  view: "overview",
  detail: null, // { name, dates, series, hot_keywords }
  range: "30d",
  kwFilter: null,
  chart: null
};

var VIEW_TITLES = {
  overview: "总览",
  categories: "类目热点",
  keywords: "热搜词",
  status: "数据状态"
};

function $(sel) { return document.querySelector(sel); }
function esc(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}
function catNameHtml(c) {
  return c.cn
    ? '<span class="cat-name">' + esc(c.cn) + '</span><span class="cat-local">' + esc(c.name) + '</span>'
    : '<span class="cat-name">' + esc(c.name) + '</span>';
}
function kwNameHtml(k) {
  return k.cn
    ? '<span class="kw-name">' + esc(k.cn) + '<small>' + esc(k.keyword) + '</small></span>'
    : '<span class="kw-name">' + esc(k.keyword) + '</span>';
}
function pct(delta, base) {
  if (base > 0) {
    var v = (delta / base) * 100;
    return (v >= 0 ? "+" : "") + v.toFixed(1) + "%";
  }
  return delta === 0 ? "持平" : "新上榜";
}
function chip(delta, base) {
  if (delta > 0.000001) return '<span class="chip up">▲ ' + pct(delta, base) + '</span>';
  if (delta < -0.000001) return '<span class="chip down">▼ ' + pct(-delta, base) + '</span>';
  return '<span class="chip flat">—</span>';
}
function marketName(code) {
  if (!state.meta) return code;
  var m = state.meta.markets.find(function (x) { return x.code === code; });
  return m ? m.label : code;
}

function setView(view) {
  state.view = view;
  document.querySelectorAll(".nav-item").forEach(function (b) {
    var on = b.getAttribute("data-view") === view;
    b.classList.toggle("active", on);
  });
  $("#page-title").innerHTML = VIEW_TITLES[view] + '<small>跨境 · Shopee</small>';
  render();
}

function renderMarkets() {
  var seg = $("#market-seg");
  seg.innerHTML = "";
  state.meta.markets.forEach(function (m) {
    var b = document.createElement("button");
    b.type = "button";
    b.textContent = m.label;
    b.dataset.market = m.code;
    b.setAttribute("aria-pressed", m.code === state.market ? "true" : "false");
    if (m.code === state.market) b.classList.add("active");
    b.addEventListener("click", function () { switchMarket(m.code); });
    seg.appendChild(b);
  });
}

function switchMarket(code) {
  state.market = code;
  state.detail = null;
  state.kwFilter = null;
  renderMarkets();
  loadMarket();
}

function loadMarket() {
  fetch("data/" + state.market + ".json")
    .then(function (r) { return r.json(); })
    .then(function (d) {
      state.data = d;
      render();
    })
    .catch(function () {
      $("#content").innerHTML = '<div class="empty">该市场数据加载失败，请稍后刷新。</div>';
    });
}

function render() {
  var content = $("#content");
  if (!state.data) {
    content.innerHTML = '<div class="empty">正在加载数据…</div>';
    return;
  }
  updateSidebar();
  if (state.view === "overview") renderOverview(content);
  else if (state.view === "categories") renderCategories(content);
  else if (state.view === "keywords") renderKeywords(content);
  else if (state.view === "status") renderStatus(content);
  if (state.chart) { state.chart.dispose(); state.chart = null; }
  if (state.detail && (state.view === "categories")) renderChart();
}

function updateSidebar() {
  var m = state.meta.markets.find(function (x) { return x.code === state.market; });
  if (!m) return;
  $("#side-status").innerHTML =
    "数据更新于 <b>" + esc(m.updated_at) + "</b><br>" +
    "历史 <b>" + m.history_days + "</b> 天 · 采集成功";
}

function statusBar(extra) {
  var d = state.data;
  return '<div class="statusbar"><span class="dot"></span><span><b>' +
    esc(marketName(state.market)) + '数据已更新</b> · ' + esc(d.updated_at) +
    (extra ? " · " + extra : "") + "</span></div>";
}

function renderOverview(content) {
  var d = state.data;
  var top = d.categories.slice(0, 5);
  var kws = d.keywords.slice(0, 10);
  var html = statusBar("历史 " + d.dates.length + " 天");
  html += '<div class="metrics">' +
    '<div class="stat"><div class="stat-label">监测类目</div><div class="stat-value">' + d.categories.length + '</div><div class="stat-delta">一级类目（含子类目下钻）</div></div>' +
    '<div class="stat"><div class="stat-label">今日热搜词</div><div class="stat-value">' + d.keywords.length + '+</div><div class="stat-delta">搜索联想词热度榜</div></div>' +
    '<div class="stat"><div class="stat-label">数据历史</div><div class="stat-value">' + d.dates.length + ' 天</div><div class="stat-delta">每日自动积累，曲线越来越准</div></div>' +
    "</div>";

  var rows = top.map(function (c) {
    return "<tr class=\"cat-row\" data-catid=\"" + c.catid + "\">" +
      "<td>" + catNameHtml(c) + "</td>" +
      "<td class=\"score\">" + c.heat.toFixed(2) + "</td>" +
      "<td style=\"text-align:right\">" + chip(c.delta, c.heat - c.delta) + "</td></tr>";
  }).join("");

  html += '<div class="grid-2">' +
    '<section class="panel"><div class="panel-head"><div><div class="panel-title">类目热点 TOP 5</div><div class="panel-sub">点击进入类目页查看全部与下钻</div></div></div>' +
    '<table><thead><tr><th>类目</th><th class="score">热度分</th><th style="text-align:right">今日变化</th></tr></thead><tbody>' + rows + "</tbody></table></section>" +
    '<section class="panel"><div class="panel-head"><div><div class="panel-title">热搜词 TOP 10</div><div class="panel-sub">搜索联想词热度</div></div></div>' +
    kws.map(function (k, i) {
      return '<div class="kw-row"><span class="kw-rank">' + (i + 1) + '</span>' +
        kwNameHtml(k) +
        '<span class="kw-heat">' + k.heat.toFixed(2) + '</span>' +
        chip(k.delta, k.heat - k.delta) + "</div>";
    }).join("") + "</section></div>";
  content.innerHTML = html;
  bindCategoryRows();
}

function renderCategories(content) {
  var d = state.data;
  var html = statusBar();
  html += '<div class="grid-2"><section class="panel"><div class="panel-head"><div><div class="panel-title">类目热点榜</div><div class="panel-sub">热度分 = 搜索联想词热度加权 · 点击类目展开子类目，点子类目看详情</div></div></div>' +
    '<table><thead><tr><th style="width:46%">类目</th><th class="score">热度分</th><th style="text-align:right">今日变化</th><th style="width:28px"></th></tr></thead><tbody>';
  d.categories.forEach(function (c, i) {
    html += '<tr class="cat-row" data-i="' + i + '">' +
      "<td>" + catNameHtml(c) + "</td>" +
      "<td class=\"score\">" + c.heat.toFixed(2) + "</td>" +
      "<td style=\"text-align:right\">" + chip(c.delta, c.heat - c.delta) + "</td>" +
      '<td style="text-align:right;color:#c0bec2">▾</td></tr>';
    c.subs.forEach(function (s, j) {
      html += '<tr class="sub-row" data-cat="' + i + '" data-j="' + j + '" hidden>' +
        '<td style="padding-left:26px">' + catNameHtml(s) + "</td>" +
        "<td class=\"score\">" + (s.heat > 0 ? s.heat.toFixed(2) : "—") + "</td>" +
        '<td style="text-align:right">' + (s.heat > 0 ? chip(s.delta, s.heat - s.delta) : '<span class="chip flat">未跟踪</span>') + "</td>" +
        "<td></td></tr>";
    });
  });
  html += "</tbody></table></section>";

  // 右栏：飙升子类目 + 热搜词速览
  var rising = [];
  d.categories.forEach(function (c, ci) {
    c.subs.forEach(function (s, si) {
      if (s.heat > 0 && s.delta > 0.000001) {
        rising.push({ ci: ci, si: si, delta: s.delta, name: s.name, cn: s.cn });
      }
    });
  });
  rising.sort(function (a, b) { return b.delta - a.delta; });
  var risingHtml = rising.slice(0, 8).map(function (r) {
    return '<div class="kw-row rising-row" data-ci="' + r.ci + '" data-si="' + r.si + '" title="点击查看详情">' +
      '<span class="kw-name">' + (r.cn ? esc(r.cn) + "<small>" + esc(r.name) + "</small>" : esc(r.name)) + "</span>" +
      '<span class="chip up">▲ ' + r.delta.toFixed(2) + "</span></div>";
  }).join("") || '<div class="empty">暂无，数据积累几天后自动出现</div>';

  var kws = d.keywords.slice(0, 8).map(function (k, i) {
    return '<div class="kw-row"><span class="kw-rank">' + (i + 1) + '</span>' +
      kwNameHtml(k) + '<span class="kw-heat">' + k.heat.toFixed(2) + "</span>" +
      chip(k.delta, k.heat - k.delta) + "</div>";
  }).join("");
  html += '<div class="right-col">' +
    '<section class="panel"><div class="panel-head"><div><div class="panel-title">飙升子类目</div><div class="panel-sub">今日涨幅最高，点击查看曲线</div></div></div>' + risingHtml + "</section>" +
    '<section class="panel"><div class="panel-head"><div><div class="panel-title">热搜词速览</div></div><button class="text-link" id="goto-kw" type="button">查看全部 →</button></div>' +
    (kws || '<div class="empty">暂无</div>') + "</section></div></div>";
  content.innerHTML = html;

  var table = content.querySelector("table");
  table.addEventListener("click", function (e) {
    var tr = e.target.closest("tr");
    if (!tr) return;
    if (tr.classList.contains("cat-row")) {
      var i = Number(tr.getAttribute("data-i"));
      var subRows = content.querySelectorAll('tr.sub-row[data-cat="' + i + '"]');
      var show = subRows[0] && subRows[0].hidden;
      content.querySelectorAll("tr.sub-row").forEach(function (r) { r.hidden = true; });
      if (show) subRows.forEach(function (r) { r.hidden = false; });
    } else if (tr.classList.contains("sub-row")) {
      var ci = Number(tr.getAttribute("data-cat"));
      var si = Number(tr.getAttribute("data-j"));
      openSub(ci, si);
    }
  });
  content.querySelectorAll(".rising-row").forEach(function (row) {
    row.addEventListener("click", function () {
      openSub(Number(row.getAttribute("data-ci")), Number(row.getAttribute("data-si")));
    });
  });
  var gotoKw = document.getElementById("goto-kw");
  if (gotoKw) gotoKw.addEventListener("click", function () { setView("keywords"); });
}

function openSub(ci, si) {
  var cat = state.data.categories[ci];
  var sub = cat.subs[si];
  state.detail = {
    name: (cat.cn ? cat.cn : cat.name) + " › " + (sub.cn ? sub.cn : sub.name),
    dates: sub.dates,
    series: sub.series,
    hot_keywords: sub.hot_keywords,
    heat: sub.heat,
    delta: sub.delta
  };
  render();
}

function renderDetail() {
  var d = state.data;
  var det = state.detail;
  var html = '<button class="back-link" id="back-btn">← 返回类目列表</button>';
  html += '<section class="panel"><div class="panel-head"><div>' +
    '<div class="panel-title">类目趋势</div>' +
    '<div class="crumb">' + esc(marketName(state.market)) + '<span class="sep">/</span>' + esc(det.name) + "</div></div>" +
    '<div class="seg" role="group" aria-label="时间范围">' +
    '<button type="button" data-range="7d" ' + (state.range === "7d" ? 'class="active" aria-pressed="true"' : 'aria-pressed="false"') + '>近 7 天</button>' +
    '<button type="button" data-range="30d" ' + (state.range === "30d" ? 'class="active" aria-pressed="true"' : 'aria-pressed="false"') + '>近 30 天</button>' +
    "</div></div>" +
    '<div id="chart" role="img" aria-label="类目热度分曲线"></div>' +
    '<div class="detail-row">' +
    "<span>热度分 <b>" + det.heat.toFixed(2) + "</b> " + chip(det.delta, det.heat - det.delta) + "</span>" +
    "<span>历史 <b>" + det.dates.length + "</b> 天</span></div>" +
    '<div class="panel-sub" style="margin-top:12px">相关热搜词</div>' +
    '<div class="kw-tags">' +
    (det.hot_keywords && det.hot_keywords.length
      ? det.hot_keywords.map(function (k) {
          return '<span class="kw-tag">' + esc(k.keyword) + " · " + k.heat.toFixed(2) + "</span>";
        }).join("")
      : '<span class="empty" style="padding:4px 0">暂无（该子类目尚未纳入每日跟踪）</span>') +
    "</div></section>";
  return html;
}

function renderChart() {
  var det = state.detail;
  var chartEl = $("#chart");
  if (!chartEl) return;
  state.chart = echarts.init(chartEl);
  var n = state.range === "7d" ? Math.min(7, det.dates.length) : det.dates.length;
  var dates = det.dates.slice(-n);
  var series = det.series.slice(-n);
  state.chart.setOption({
    grid: { left: 46, right: 18, top: 20, bottom: 26 },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: dates, axisLine: { lineStyle: { color: "#e5e2e4" } }, axisLabel: { color: "#909097" } },
    yAxis: { type: "value", min: 0, splitLine: { lineStyle: { color: "#eeebed" } }, axisLabel: { color: "#909097" } },
    series: [{
      type: "line",
      data: series,
      smooth: true,
      symbol: "circle",
      symbolSize: 5,
      lineStyle: { width: 2, color: "#10a37f" },
      itemStyle: { color: "#10a37f" },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: "rgba(16,163,127,0.22)" },
          { offset: 1, color: "rgba(16,163,127,0.02)" }
        ])
      }
    }]
  });
}

function renderKeywords(content) {
  var d = state.data;
  var html = statusBar();
  var chips = ['<button type="button" class="chip-cat' + (!state.kwFilter ? " active" : "") + '" data-cat="">全部</button>'];
  d.categories.forEach(function (c) {
    chips.push('<button type="button" class="chip-cat' + (state.kwFilter === c.name ? " active" : "") + '" data-cat="' + esc(c.name) + '">' +
      (c.cn ? esc(c.cn) : esc(c.name)) + "</button>");
  });
  var list = state.kwFilter
    ? d.keywords.filter(function (k) { return (k.cats || []).indexOf(state.kwFilter) >= 0; })
    : d.keywords;
  html += '<section class="panel"><div class="panel-head"><div><div class="panel-title">热搜词榜</div><div class="panel-sub">按今日搜索联想词热度排序 · 点击类目筛选</div></div></div>';
  html += '<div class="chip-cat-row">' + chips.join("") + "</div>";
  if (list.length === 0) {
    html += '<div class="empty">该类目暂无热搜词数据，明天更新后会出现</div>';
  }
  list.forEach(function (k, i) {
    html += '<div class="kw-row"><span class="kw-rank">' + (i + 1) + '</span>' +
      kwNameHtml(k) +
      '<span class="kw-heat">' + k.heat.toFixed(2) + '</span>' +
      chip(k.delta, k.heat - k.delta) + "</div>";
  });
  html += "</section>";
  content.innerHTML = html;
  content.querySelectorAll(".chip-cat").forEach(function (b) {
    b.addEventListener("click", function () {
      state.kwFilter = b.getAttribute("data-cat") || null;
      render();
    });
  });
}

function renderStatus(content) {
  var html = statusBar("各市场数据状态");
  html += '<div class="status-grid">' +
    state.meta.markets.map(function (m) {
      return '<div class="status-card"><h3>' + esc(m.label) + "（" + esc(m.name) + "）</h3>" +
        "<p>最近更新：<b>" + esc(m.updated_at) + "</b></p>" +
        "<p>类目数量：<b>" + m.n_categories + "</b></p>" +
        "<p>热搜词：<b>" + m.n_keywords + "</b></p>" +
        "<p>数据历史：<b>" + m.history_days + "</b> 天</p></div>";
    }).join("") + "</div>";
  html += '<div class="panel" style="margin-top:14px"><div class="panel-title">数据说明</div>' +
    '<p class="panel-sub" style="margin:8px 0 0">当前数据全部来自 Shopee 公开接口（类目树 + 搜索联想词），每天自动更新一次。热度分为相对值，用于站内排序，不代表销量。连续多日后，涨跌曲线会越来越有参考价值。</p></div>';
  content.innerHTML = html;
}

function bindCategoryRows() {
  document.querySelectorAll("tr.cat-row").forEach(function (tr) {
    tr.addEventListener("click", function () { setView("categories"); });
  });
}

function init() {
  fetch("data/meta.json")
    .then(function (r) { return r.json(); })
    .then(function (meta) {
      state.meta = meta;
      state.market = meta.markets[0].code;
      renderMarkets();
      return loadMarket();
    });

  document.querySelectorAll(".nav-item").forEach(function (b) {
    b.addEventListener("click", function () { setView(b.getAttribute("data-view")); });
  });

  var logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", function () {
      localStorage.removeItem("ecom_auth");
      location.href = "login.html";
    });
  }

  var settingsBtn = document.getElementById("settings-btn");
  var settingsMenu = document.getElementById("settings-menu");
  if (settingsBtn && settingsMenu) {
    settingsBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      settingsMenu.hidden = !settingsMenu.hidden;
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest("#settings-menu") && !e.target.closest("#settings-btn")) {
        settingsMenu.hidden = true;
      }
    });
  }

  $("#content").addEventListener("click", function (e) {
    var rangeBtn = e.target.closest("button[data-range]");
    if (rangeBtn) {
      state.range = rangeBtn.getAttribute("data-range");
      render();
      return;
    }
    if (e.target.closest("#back-btn")) {
      state.detail = null;
      render();
    }
  });
  window.addEventListener("resize", function () {
    if (state.chart) state.chart.resize();
  });
}

init();
