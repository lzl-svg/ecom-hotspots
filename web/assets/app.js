"use strict";

var DATA_VERSION = "9";

// 首次打开时的演示监控池；用户可在“核心类目日榜”中多选并保存。
var CORE_WATCHLIST = {
  id: [11044245, 11043573, 11043032, 11043959, 11042643, 11042901],
  my: [11000691, 11133423, 11001537, 11000989, 11000746, 11000711],
  vn: [11036102, 11036280, 11036479, 11035742, 11036526, 11035899],
  ozon: [],
  wb: []
};

var state = {
  meta: null,
  market: null,
  data: null,
  view: "overview",
  detail: null,
  weeklyParent: null,
  weeklyFilter: "week",
  coreParent: null,
  watchlistMessage: "",
  watchlistSaving: false,
  chart: null
};

var VIEW_TITLES = {
  overview: "市场总览",
  core: "核心类目日榜",
  weekly: "全市场周榜",
  method: "口径与状态"
};

function $(selector) { return document.querySelector(selector); }

function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
  });
}

function displayName(item) {
  return item.cn || item.name || "未命名类目";
}

function localName(item) {
  if (item.cn && item.name && item.cn !== item.name) return item.name;
  return "";
}

function nameHTML(item) {
  return '<div class="name-stack"><b>' + esc(displayName(item)) + '</b>' +
    (localName(item) ? '<small>' + esc(localName(item)) + '</small>' : "") + '</div>';
}

function marketMeta() {
  if (!state.meta) return null;
  return state.meta.markets.find(function (item) { return item.code === state.market; }) || null;
}

function isPublicCatalogMarket() {
  return state.market === "ozon" || state.market === "wb";
}

function signalLabel() {
  return isPublicCatalogMarket() ? "公开商品信号" : "搜索联想信号";
}

function sourceExplanation() {
  if (state.data && state.data.signal_definition) return state.data.signal_definition;
  return "Shopee 搜索联想词的覆盖数量和出现位置合成活跃度；仅用于市场内相对比较，不代表搜索量、销量或销售额。";
}

function normalizeWatchlist(payload) {
  var result = { id: [], my: [], vn: [], ozon: [], wb: [] };
  Object.keys(result).forEach(function (market) {
    var values = payload && Array.isArray(payload[market]) ? payload[market] : [];
    result[market] = Array.from(new Set(values.map(Number).filter(Number.isFinite)));
  });
  return result;
}

function loadWatchlist() {
  var local = null;
  try {
    var raw = localStorage.getItem("category-radar-watchlist");
    if (raw) local = normalizeWatchlist(JSON.parse(raw));
  } catch (error) { local = null; }
  return fetch("api/watchlist?v=" + Date.now(), { cache: "no-store" })
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then(function (saved) { CORE_WATCHLIST = normalizeWatchlist(saved); })
    .catch(function () { if (local) CORE_WATCHLIST = local; });
}

function saveWatchlist() {
  state.watchlistSaving = true;
  state.watchlistMessage = "正在保存采集清单…";
  try { localStorage.setItem("category-radar-watchlist", JSON.stringify(CORE_WATCHLIST)); } catch (error) { /* local backup is optional */ }
  render();
  fetch("api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(CORE_WATCHLIST)
  })
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then(function (result) {
      CORE_WATCHLIST = normalizeWatchlist(result.watchlist || CORE_WATCHLIST);
      state.watchlistSaving = false;
      state.watchlistMessage = "已保存：下次采集会读取这份固定小类目清单";
      render();
    })
    .catch(function () {
      state.watchlistSaving = false;
      state.watchlistMessage = "已保存在当前浏览器；本地采集配置暂未同步";
      render();
    });
}

function observed(item) {
  var dates = item.dates || [];
  var series = item.series || [];
  var result = [];
  for (var i = 0; i < Math.min(dates.length, series.length); i += 1) {
    if (Number.isFinite(series[i])) result.push({ date: dates[i], value: Number(series[i]) });
  }
  return result;
}

function mean(values) {
  if (!values.length) return null;
  return values.reduce(function (sum, value) { return sum + value; }, 0) / values.length;
}

function itemStats(item) {
  var points = observed(item);
  var values = points.map(function (point) { return point.value; });
  var last = values.length ? values[values.length - 1] : null;
  var previous = values.length > 1 ? values[values.length - 2] : null;
  var delta = last != null && previous != null ? last - previous : null;
  var pct = delta != null && previous > 0 ? delta / previous * 100 : null;
  var streak = 0;
  for (var i = values.length - 1; i > 0; i -= 1) {
    if (values[i] > values[i - 1]) streak += 1;
    else break;
  }
  return {
    points: points,
    last: last,
    previous: previous,
    delta: delta,
    pct: pct,
    avg7: mean(values.slice(-7)),
    avg30: mean(values.slice(-30)),
    streak: streak,
    sampleCount: values.length,
    lastDate: item.last_tracked_date || (points.length ? points[points.length - 1].date : ""),
    previousDate: points.length > 1 ? points[points.length - 2].date : ""
  };
}

function score100(value, maxValue) {
  if (!(value > 0) || !(maxValue > 0)) return 0;
  return Math.round(value / maxValue * 100);
}

function scoreBar(score) {
  return '<div class="score-cell"><b>' + score + '</b><span><i style="width:' + score + '%"></i></span></div>';
}

function changeChip(stats) {
  if (stats.delta == null) return '<span class="badge neutral">积累中</span>';
  var comparison = stats.previousDate && stats.lastDate ? stats.previousDate + " → " + stats.lastDate : "最近两次有效样本";
  if (Math.abs(stats.delta) < 0.000001) return '<span class="badge neutral" title="' + esc(comparison) + '：活跃度数值相同">持平</span>';
  var label = stats.pct == null ? Math.abs(stats.delta).toFixed(2) : Math.abs(stats.pct).toFixed(1) + "%";
  if (stats.delta > 0) return '<span class="badge up" title="' + esc(comparison) + '">↑ ' + label + '</span>';
  return '<span class="badge down" title="' + esc(comparison) + '">↓ ' + label + '</span>';
}

function trendDefinition() {
  return '<p class="trend-definition"><b>趋势口径：</b>比较最近两次有效采集；“持平”表示活跃度数值在当前记录精度下完全相同。轮询类目的两次样本不一定相隔1天。</p>';
}

function freshness(item) {
  var stats = itemStats(item);
  var today = state.data && state.data.dates && state.data.dates[0];
  var recentDates = new Set((state.data && state.data.dates || []).slice(0, 7));
  if (!stats.lastDate) return { key: "none", label: "暂无数据", className: "muted" };
  if (stats.lastDate === today) return { key: "today", label: "今日", className: "fresh" };
  if (recentDates.has(stats.lastDate)) return { key: "week", label: "本周 " + stats.lastDate.slice(5), className: "weekly" };
  return { key: "old", label: stats.lastDate, className: "muted" };
}

function freshnessChip(item) {
  var fresh = freshness(item);
  return '<span class="freshness ' + fresh.className + '">' + esc(fresh.label) + '</span>';
}

function selectedCoreIds() {
  return new Set((CORE_WATCHLIST[state.market] || []).map(Number));
}

function setCoreSelection(catid, selected) {
  var ids = selectedCoreIds();
  if (selected) ids.add(Number(catid));
  else ids.delete(Number(catid));
  CORE_WATCHLIST[state.market] = Array.from(ids);
  state.watchlistMessage = "有未保存的更改";
}

function currentCoreParent() {
  var parents = state.data.categories || [];
  var selected = parents.find(function (parent) { return Number(parent.catid) === Number(state.coreParent); });
  if (!selected && parents.length) {
    selected = parents[0];
    state.coreParent = selected.catid;
  }
  return selected || null;
}

function setCurrentParentSelection(selected) {
  var parent = currentCoreParent();
  if (!parent) return;
  var ids = selectedCoreIds();
  (parent.subs || []).forEach(function (sub) {
    if (selected) ids.add(Number(sub.catid));
    else ids.delete(Number(sub.catid));
  });
  CORE_WATCHLIST[state.market] = Array.from(ids);
  state.watchlistMessage = "有未保存的更改";
}

function renderWatchlistConfigurator() {
  var parents = state.data.categories || [];
  var parent = currentCoreParent();
  if (!parent) return '<section class="panel"><div class="empty-state">暂无可选择的小类目</div></section>';
  var ids = selectedCoreIds();
  var selectedInParent = (parent.subs || []).filter(function (sub) { return ids.has(Number(sub.catid)); }).length;
  var messageClass = state.watchlistMessage.indexOf("已保存：") === 0 ? "saved" : (state.watchlistMessage ? "pending" : "");
  return '<section class="panel watchlist-panel"><div class="panel-head"><div><span class="section-kicker">COLLECTION WATCHLIST</span>' +
    '<h3>选择需要每日连续采集的小类目</h3><p>可跨多个大类勾选，支持只选1个或同时选择多个；保存后其余小类目继续按周轮询。</p></div>' +
    '<span class="selection-count">已选 <b>' + ids.size + '</b> 个</span></div>' +
    '<div class="watchlist-toolbar"><label class="select-label">先选择一级类目<select id="core-parent-select">' + parents.map(function (item) {
      return '<option value="' + item.catid + '"' + (Number(item.catid) === Number(parent.catid) ? ' selected' : '') + '>' + esc(displayName(item)) + '</option>';
    }).join("") + '</select></label><div class="watchlist-actions">' +
    '<button type="button" data-watch-action="select-all">全选当前大类</button>' +
    '<button type="button" data-watch-action="clear-parent">清空当前大类</button></div></div>' +
    '<div class="watchlist-summary"><b>' + esc(displayName(parent)) + '</b><span>已选 ' + selectedInParent + ' / ' + (parent.subs || []).length + '</span></div>' +
    '<div class="watchlist-options">' + (parent.subs || []).map(function (sub) {
      var checked = ids.has(Number(sub.catid));
      return '<label class="watch-option' + (checked ? ' selected' : '') + '"><input type="checkbox" data-watch-sub="' + sub.catid + '"' + (checked ? ' checked' : '') + '>' +
        '<span><b>' + esc(displayName(sub)) + '</b>' + (localName(sub) ? '<small>' + esc(localName(sub)) + '</small>' : '') + '</span><i>' + (checked ? '每日采集' : '周轮询') + '</i></label>';
    }).join("") + '</div><div class="watchlist-savebar"><span class="save-message ' + messageClass + '">' + esc(state.watchlistMessage || "勾选后点击保存，采集程序会自动读取") + '</span>' +
    '<button class="save-watchlist" type="button" data-watch-action="save"' + (state.watchlistSaving ? ' disabled' : '') + '>' + (state.watchlistSaving ? '保存中…' : '保存采集清单') + '</button></div></section>';
}

function getCoreRows() {
  var ids = new Set(CORE_WATCHLIST[state.market] || []);
  var rows = [];
  (state.data.categories || []).forEach(function (parent) {
    (parent.subs || []).forEach(function (sub) {
      if (ids.has(Number(sub.catid))) rows.push({ parent: parent, item: sub });
    });
  });
  return rows;
}

function flattenSubs() {
  var rows = [];
  (state.data.categories || []).forEach(function (parent) {
    (parent.subs || []).forEach(function (sub) { rows.push({ parent: parent, item: sub }); });
  });
  return rows;
}

function rootRankRows() {
  var roots = (state.data.categories || []).slice();
  var current = roots.slice().sort(function (a, b) { return (b.heat || 0) - (a.heat || 0); });
  var previous = roots.slice().sort(function (a, b) {
    return (itemStats(b).previous || 0) - (itemStats(a).previous || 0);
  });
  var previousRank = {};
  previous.forEach(function (item, index) { previousRank[item.catid] = index + 1; });
  var maxHeat = current.length ? current[0].heat || 0 : 0;
  return current.map(function (item, index) {
    return {
      item: item,
      rank: index + 1,
      previousRank: previousRank[item.catid] || null,
      movement: previousRank[item.catid] ? previousRank[item.catid] - (index + 1) : null,
      score: score100(item.heat || 0, maxHeat),
      stats: itemStats(item)
    };
  });
}

function rankMove(move) {
  if (move == null) return '<span class="rank-move neutral">—</span>';
  if (move > 0) return '<span class="rank-move up">↑ ' + move + '</span>';
  if (move < 0) return '<span class="rank-move down">↓ ' + Math.abs(move) + '</span>';
  return '<span class="rank-move neutral">—</span>';
}

function dataRibbon(extra) {
  var degraded = state.data && state.data.source_status === "degraded";
  var warming = state.data && state.data.source_status === "warming";
  var status = degraded ? '<span class="badge down">数据源受限</span>' : (warming ? '<span class="badge neutral">等待首采</span>' : '');
  var note = (degraded || warming) && state.data.source_note ? state.data.source_note : (extra || "一级类目每日更新 · 小类目分层监控");
  return '<div class="data-ribbon"><div><span class="live-dot"></span><b>' +
    esc((marketMeta() || {}).label || state.market) + '</b><span>最近有效数据 ' +
    esc(state.data.updated_at || "—") + '</span>' + status + '</div><small>' +
    esc(note) + '</small></div>';
}

function renderOverview() {
  var roots = rootRankRows();
  var core = getCoreRows();
  var allSubs = flattenSubs();
  var weeklyCovered = allSubs.filter(function (row) {
    var key = freshness(row.item).key;
    return key === "today" || key === "week";
  }).length;
  var coverage = allSubs.length ? Math.round(weeklyCovered / allSubs.length * 100) : 0;
  var coreMax = Math.max.apply(null, core.map(function (row) { return row.item.heat || 0; }).concat([0]));
  var coreSignals = core.slice().sort(function (a, b) {
    return (itemStats(b.item).pct || 0) - (itemStats(a.item).pct || 0);
  });

  var html = dataRibbon("活跃度仅用于同一市场内相对比较，不代表真实销量");
  html += '<section class="hero"><div><span class="section-kicker">MARKET PULSE</span>' +
    '<h2>先看大类方向，再下钻固定小类目</h2>' +
    '<p>一级类目保持每日完整排行；公司的固定小类目连续跟踪；其余小类目以滚动周榜负责发现机会。</p></div>' +
    '<button class="primary-btn" type="button" data-go="core">查看核心日榜 →</button></section>';

  html += '<div class="metric-grid">' +
    metricCard("一级类目", roots.length, "每日完整比较", "indigo") +
    metricCard("固定小类目", core.length, "当前已选监控池", "green") +
    metricCard("连续历史", state.data.dates.length + "天", "最长保留30天", "orange") +
    metricCard("本周覆盖", coverage + "%", weeklyCovered + " / " + allSubs.length + " 个小类目", "blue") +
    '</div>';

  html += '<div class="dashboard-grid"><section class="panel wide"><div class="panel-head"><div>' +
    '<span class="section-kicker">DAILY RANKING</span><h3>一级类目活跃度日榜</h3>' +
    '<p>所有一级类目使用同一天数据，排名可以连续比较。</p></div><span class="scope-chip">市场内标准化 0–100</span></div>' +
    trendDefinition() +
    '<div class="table-wrap"><table><thead><tr><th>排名</th><th>一级类目</th><th>活跃度</th><th>较上次</th><th>趋势</th></tr></thead><tbody>' +
    roots.slice(0, 10).map(function (row) {
      return '<tr class="clickable" data-open-root="' + row.item.catid + '"><td><span class="rank-num">' + row.rank + '</span></td>' +
        '<td>' + nameHTML(row.item) + '</td><td>' + scoreBar(row.score) + '</td><td>' + rankMove(row.movement) + '</td><td>' + changeChip(row.stats) + '</td></tr>';
    }).join("") + '</tbody></table></div></section>';

  html += '<section class="panel"><div class="panel-head"><div><span class="section-kicker">CORE SIGNALS</span>' +
    '<h3>固定小类目信号</h3><p>连续采集，避免跌出热门后产生数据断档。</p></div></div><div class="signal-list">' +
    (coreSignals.length ? coreSignals.map(function (row, index) {
      var stats = itemStats(row.item);
      return '<button type="button" class="signal-row" data-open-sub="' + row.item.catid + '"><span class="signal-rank">' + (index + 1) + '</span>' +
        '<span class="signal-name">' + esc(displayName(row.item)) + '<small>' + esc(displayName(row.parent)) + '</small></span>' +
        '<span class="signal-score">' + score100(row.item.heat || 0, coreMax) + '</span>' + changeChip(stats) + '</button>';
    }).join("") : '<div class="empty-state">还没有选择固定小类目，请到核心类目日榜中添加。</div>') + '</div></section></div>';
  return html;
}

function metricCard(label, value, note, tone) {
  return '<article class="metric-card ' + tone + '"><span>' + esc(label) + '</span><strong>' + esc(value) + '</strong><small>' + esc(note) + '</small></article>';
}

function renderCore() {
  var rows = getCoreRows();
  var maxHeat = Math.max.apply(null, rows.map(function (row) { return row.item.heat || 0; }).concat([0]));
  rows.sort(function (a, b) { return (b.item.heat || 0) - (a.item.heat || 0); });

  var html = dataRibbon("固定小类目可自由多选，保存后进入每日连续采集池");
  html += renderWatchlistConfigurator();
  html += '<section class="panel"><div class="panel-head"><div><span class="section-kicker">CONTINUOUS TRACKING</span>' +
    '<h3>核心小类目连续日榜</h3><p>排名仅在固定监控池内比较，所有类目保持连续数据。</p></div>' +
    '<span class="scope-chip">每日固定采集</span></div>' + trendDefinition() + (rows.length ? '<div class="table-wrap"><table><thead><tr>' +
    '<th>日榜</th><th>小类目</th><th>所属大类</th><th>活跃度</th><th>7日均值</th><th>连续样本</th><th>变化</th><th>新鲜度</th>' +
    '</tr></thead><tbody>' + rows.map(function (row, index) {
      var stats = itemStats(row.item);
      return '<tr class="clickable" data-open-sub="' + row.item.catid + '"><td><span class="rank-num">' + (index + 1) + '</span></td>' +
        '<td>' + nameHTML(row.item) + '</td><td><span class="parent-label">' + esc(displayName(row.parent)) + '</span></td>' +
        '<td>' + scoreBar(score100(row.item.heat || 0, maxHeat)) + '</td><td class="number">' + (stats.avg7 == null ? "—" : stats.avg7.toFixed(2)) + '</td>' +
        '<td><b class="number">' + stats.sampleCount + '</b><small class="unit"> 天</small></td><td>' + changeChip(stats) + '</td><td>' + freshnessChip(row.item) + '</td></tr>';
    }).join("") + '</tbody></table></div>' : '<div class="empty-state">当前市场还没有选择固定小类目。请在上方勾选一个或多个类目并保存。</div>') + '</section>';
  return html;
}

function renderWeekly() {
  var parents = state.data.categories || [];
  if (!state.weeklyParent && parents.length) state.weeklyParent = parents[0].catid;
  var selected = parents.find(function (parent) { return Number(parent.catid) === Number(state.weeklyParent); }) || parents[0];
  if (!selected) return dataRibbon() + '<div class="empty-state">暂无类目数据</div>';

  var rows = (selected.subs || []).map(function (item) { return { item: item, stats: itemStats(item), fresh: freshness(item) }; });
  rows = rows.filter(function (row) {
    if (state.weeklyFilter === "today") return row.fresh.key === "today";
    if (state.weeklyFilter === "week") return row.fresh.key === "today" || row.fresh.key === "week";
    return row.stats.sampleCount > 0;
  });
  rows.sort(function (a, b) { return (b.item.heat || 0) - (a.item.heat || 0); });
  var maxHeat = Math.max.apply(null, rows.map(function (row) { return row.item.heat || 0; }).concat([0]));

  var html = dataRibbon("滚动周榜使用每个小类目本周最近一次有效采集");
  html += '<section class="panel"><div class="panel-head weekly-tools"><div><span class="section-kicker">ROLLING WEEKLY DISCOVERY</span>' +
    '<h3>大类内部小类目周榜</h3><p>用于观察完整市场，日期不同的数据不会伪装成同一日榜。</p></div>' +
    '<label class="select-label">选择一级类目<select id="parent-select">' + parents.map(function (parent) {
      return '<option value="' + parent.catid + '"' + (Number(parent.catid) === Number(selected.catid) ? ' selected' : '') + '>' + esc(displayName(parent)) + '</option>';
    }).join("") + '</select></label></div>' +
    '<div class="filter-row"><button type="button" data-week-filter="today" class="' + (state.weeklyFilter === "today" ? "active" : "") + '">今日采集</button>' +
    '<button type="button" data-week-filter="week" class="' + (state.weeklyFilter === "week" ? "active" : "") + '">本周覆盖</button>' +
    '<button type="button" data-week-filter="all" class="' + (state.weeklyFilter === "all" ? "active" : "") + '">全部历史</button></div>';

  html += rows.length ? '<div class="table-wrap"><table><thead><tr><th>周榜</th><th>小类目</th><th>活跃度</th><th>最近采集</th><th>有效样本</th><th>趋势</th></tr></thead><tbody>' +
    rows.map(function (row, index) {
      return '<tr class="clickable" data-open-sub="' + row.item.catid + '"><td><span class="rank-num">' + (index + 1) + '</span></td>' +
        '<td>' + nameHTML(row.item) + '</td><td>' + scoreBar(score100(row.item.heat || 0, maxHeat)) + '</td><td>' + freshnessChip(row.item) + '</td>' +
        '<td><b class="number">' + row.stats.sampleCount + '</b><small class="unit"> 天</small></td><td>' + changeChip(row.stats) + '</td></tr>';
    }).join("") + '</tbody></table></div>' : '<div class="empty-state">当前筛选范围内还没有有效采集数据</div>';
  html += trendDefinition();
  html += '</section>';
  return html;
}

function renderMethod() {
  var roots = rootRankRows();
  var allSubs = flattenSubs();
  var todayCount = allSubs.filter(function (row) { return freshness(row.item).key === "today"; }).length;
  var weekCount = allSubs.filter(function (row) {
    var key = freshness(row.item).key;
    return key === "today" || key === "week";
  }).length;
  var html = dataRibbon("透明展示数据来源、更新时间和限制");
  html += '<div class="method-grid"><section class="panel"><span class="section-kicker">WHAT IT MEANS</span><h3>这个排行代表什么</h3>' +
    '<p class="body-copy">' + esc(sourceExplanation()) + '</p>' +
    '<div class="formula">' + (isPublicCatalogMarket() ? '热门排序越靠前、反馈与类目规模信号越强 → 活跃度指数越高' : '联想词越丰富、位置越靠前 → 活跃度指数越高') + '</div>' + trendDefinition() + '</section>' +
    '<section class="panel"><span class="section-kicker">COLLECTION LAYERS</span><h3>连续性设计</h3><ul class="method-list">' +
    '<li><b>一级类目</b><span>全部每日采集，形成可比较日榜</span></li>' +
    '<li><b>固定小类目</b><span>公司监控池每日采集，避免数据断档</span></li>' +
    '<li><b>其他小类目</b><span>7天滚动覆盖，用于市场发现</span></li></ul></section></div>';
  html += '<section class="panel"><div class="panel-head"><div><span class="section-kicker">DATA HEALTH</span><h3>当前数据状态</h3></div></div>' +
    '<div class="health-grid">' + healthItem("一级类目", roots.length + " 个", "每日完整") +
    healthItem("今日小类目", todayCount + " 个", "最近成功日") + healthItem("本周小类目", weekCount + " 个", "滚动7天") +
    healthItem("历史长度", state.data.dates.length + " 天", "最长30天") + '</div>' +
    '<div class="rule-note"><b>失败保护：</b>接口失败时应保留上一份有效数据，缺失日期显示为空白，不用0或推测值补齐。</div></section>';
  return html;
}

function healthItem(label, value, note) {
  return '<div class="health-item"><span>' + esc(label) + '</span><b>' + esc(value) + '</b><small>' + esc(note) + '</small></div>';
}

function findItemById(catid) {
  var found = null;
  (state.data.categories || []).some(function (parent) {
    if (Number(parent.catid) === Number(catid)) {
      found = { parent: null, item: parent, level: 1 };
      return true;
    }
    var sub = (parent.subs || []).find(function (item) { return Number(item.catid) === Number(catid); });
    if (sub) {
      found = { parent: parent, item: sub, level: 2 };
      return true;
    }
    return false;
  });
  return found;
}

function openDetail(catid) {
  state.detail = findItemById(catid);
  render();
}

function renderDetail() {
  var detail = state.detail;
  var item = detail.item;
  var stats = itemStats(item);
  var fresh = freshness(item);
  var title = detail.parent ? displayName(detail.parent) + " / " + displayName(item) : displayName(item);
  var keywords = (item.hot_keywords || []).slice(0, 12);
  var html = '<button class="back-btn" type="button" data-back>← 返回' + esc(VIEW_TITLES[state.view]) + '</button>';
  html += '<section class="detail-hero"><div><span class="section-kicker">CATEGORY DETAIL</span><h2>' + esc(title) + '</h2>' +
    '<p>' + (detail.level === 1 ? "一级类目每日连续观察" : "小类目趋势与" + signalLabel()) + '</p></div>' + freshnessChip(item) + '</section>';
  html += '<div class="detail-metrics">' + metricCard("当前指数", stats.last == null ? "—" : stats.last.toFixed(2), isPublicCatalogMarket() ? "公开商品综合指数" : "原始联想指数", "indigo") +
    metricCard("7日均值", stats.avg7 == null ? "—" : stats.avg7.toFixed(2), "仅使用有效采集日", "green") +
    metricCard("连续上涨", stats.streak + "次", "相邻有效样本", "orange") +
    metricCard("有效样本", stats.sampleCount + "天", "最近采集 " + (stats.lastDate || "—"), "blue") + '</div>';
  html += '<section class="panel"><div class="panel-head"><div><span class="section-kicker">TREND</span><h3>最近30天活跃度</h3>' +
    '<p>断档日期保持为空，不进行推测补值。</p></div><span class="freshness ' + fresh.className + '">' + esc(fresh.label) + '</span></div>' +
    '<div id="trend-chart" class="trend-chart"></div></section>';
  html += '<section class="panel keyword-panel"><div class="panel-head"><div><span class="section-kicker">RELATED SIGNALS</span><h3>' + (isPublicCatalogMarket() ? '热门商品信号' : '类目相关搜索信号') + '</h3>' +
    '<p>' + (isPublicCatalogMarket() ? '展示公开热门排序中的代表商品，用于解释指数构成，不代表真实销量。' : '用于解释类目内部当前关注方向，不单独作为全市场热搜榜。') + '</p></div></div><div class="keyword-cloud">' +
    (keywords.length ? keywords.map(function (keyword) { return '<span>' + esc(keyword.keyword) + '<small>' + Number(keyword.heat || 0).toFixed(2) + '</small></span>'; }).join("") : '<div class="empty-state">该类目最近一次采集没有返回可用信号</div>') +
    '</div></section>';
  return html;
}

function renderChart() {
  if (state.chart) { state.chart.dispose(); state.chart = null; }
  if (!state.detail) return;
  var element = $("#trend-chart");
  if (!element || typeof echarts === "undefined") return;
  var stats = itemStats(state.detail.item);
  state.chart = echarts.init(element);
  state.chart.setOption({
    animationDuration: 450,
    grid: { left: 42, right: 18, top: 26, bottom: 34 },
    tooltip: { trigger: "axis", backgroundColor: "#172033", borderWidth: 0, textStyle: { color: "#fff" } },
    xAxis: { type: "category", data: (state.detail.item.dates || []).slice(-30), boundaryGap: false, axisLine: { lineStyle: { color: "#d8deea" } }, axisLabel: { color: "#7b8495", hideOverlap: true } },
    yAxis: { type: "value", min: 0, axisLabel: { color: "#7b8495" }, splitLine: { lineStyle: { color: "#edf0f5" } } },
    series: [{
      type: "line",
      data: (state.detail.item.series || []).slice(-30),
      connectNulls: false,
      smooth: 0.28,
      symbolSize: 6,
      lineStyle: { color: "#4f46e5", width: 3 },
      itemStyle: { color: "#4f46e5", borderColor: "#fff", borderWidth: 2 },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(79,70,229,.22)" }, { offset: 1, color: "rgba(79,70,229,0)" }]) }
    }]
  });
  if (!stats.points.length) element.innerHTML = '<div class="empty-state">暂无趋势数据</div>';
}

function render() {
  var content = $("#content");
  if (!state.data) {
    content.innerHTML = '<div class="loading-card">正在加载市场数据…</div>';
    return;
  }
  $("#page-title").textContent = state.detail ? "类目详情" : VIEW_TITLES[state.view];
  if (state.detail) content.innerHTML = renderDetail();
  else if (state.view === "overview") content.innerHTML = renderOverview();
  else if (state.view === "core") content.innerHTML = renderCore();
  else if (state.view === "weekly") content.innerHTML = renderWeekly();
  else content.innerHTML = renderMethod();
  updateSidebar();
  if (state.detail) window.setTimeout(renderChart, 0);
}

function updateSidebar() {
  var meta = marketMeta();
  $("#side-market").textContent = meta ? meta.label : state.market;
  var prefix = state.data.source_status === "degraded" ? "数据源受限 · " : (state.data.source_status === "warming" ? "等待首次采集 · " : "最近更新 ");
  $("#side-status").textContent = prefix + (state.data.updated_at || "—");
}

function renderMarkets() {
  var switcher = $("#market-switch");
  switcher.innerHTML = state.meta.markets.map(function (market) {
    return '<button type="button" data-market="' + market.code + '" class="' + (market.code === state.market ? "active" : "") + '" aria-pressed="' + (market.code === state.market) + '">' + esc(market.label) + '</button>';
  }).join("");
}

function loadMarket(code) {
  state.market = code;
  state.data = null;
  state.detail = null;
  state.weeklyParent = null;
  state.coreParent = null;
  state.watchlistMessage = "";
  renderMarkets();
  render();
  fetch("data/" + code + ".json?v=" + DATA_VERSION)
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then(function (data) { state.data = data; render(); })
    .catch(function (error) {
      $("#content").innerHTML = '<div class="error-card"><b>市场数据加载失败</b><p>' + esc(error.message) + '</p></div>';
    });
}

function setView(view) {
  state.view = view;
  state.detail = null;
  document.querySelectorAll(".nav-item").forEach(function (button) {
    button.classList.toggle("active", button.getAttribute("data-view") === view);
  });
  render();
}

function initEvents() {
  document.querySelectorAll(".nav-item").forEach(function (button) {
    button.addEventListener("click", function () { setView(button.getAttribute("data-view")); });
  });
  $("#market-switch").addEventListener("click", function (event) {
    var button = event.target.closest("button[data-market]");
    if (button && button.getAttribute("data-market") !== state.market) loadMarket(button.getAttribute("data-market"));
  });
  $("#content").addEventListener("click", function (event) {
    var root = event.target.closest("[data-open-root]");
    var sub = event.target.closest("[data-open-sub]");
    var go = event.target.closest("[data-go]");
    var filter = event.target.closest("[data-week-filter]");
    var watchAction = event.target.closest("[data-watch-action]");
    if (root) openDetail(root.getAttribute("data-open-root"));
    else if (sub) openDetail(sub.getAttribute("data-open-sub"));
    else if (go) setView(go.getAttribute("data-go"));
    else if (filter) { state.weeklyFilter = filter.getAttribute("data-week-filter"); render(); }
    else if (watchAction) {
      var action = watchAction.getAttribute("data-watch-action");
      if (action === "save") saveWatchlist();
      else if (action === "select-all") { setCurrentParentSelection(true); render(); }
      else if (action === "clear-parent") { setCurrentParentSelection(false); render(); }
    }
    else if (event.target.closest("[data-back]")) { state.detail = null; render(); }
  });
  $("#content").addEventListener("change", function (event) {
    if (event.target.id === "parent-select") { state.weeklyParent = Number(event.target.value); render(); }
    else if (event.target.id === "core-parent-select") { state.coreParent = Number(event.target.value); render(); }
    else if (event.target.matches("[data-watch-sub]")) {
      setCoreSelection(event.target.getAttribute("data-watch-sub"), event.target.checked);
      render();
    }
  });
  window.addEventListener("resize", function () { if (state.chart) state.chart.resize(); });
}

function init() {
  initEvents();
  Promise.all([loadWatchlist(), fetch("data/meta.json?v=" + DATA_VERSION).then(function (response) { return response.json(); })])
    .then(function (results) {
      var meta = results[1];
      state.meta = meta;
      loadMarket(meta.markets[0].code);
    })
    .catch(function () {
      $("#content").innerHTML = '<div class="error-card"><b>无法读取市场清单</b><p>请通过“打开网站.bat”启动本地预览。</p></div>';
    });
}

init();
