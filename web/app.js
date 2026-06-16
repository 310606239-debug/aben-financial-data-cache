const state = {
  symbol: "AAPL",
  direction: "forward",
  model: "free_cash_flow",
  years: 10,
  growthRate: 0.1,
  netMargin: 0.25,
  terminalMultiple: 25,
  discountRate: 0.12,
  data: null,
};

const $ = (id) => document.getElementById(id);
const money = (value, currency) =>
  new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
const percent = (value) =>
  value == null ? "—" : `${(value * 100).toFixed(1)}%`;
const compact = (value, currency) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("zh-CN", {
        style: "currency",
        currency,
        notation: "compact",
        maximumFractionDigits: 1,
      }).format(value);

function forwardFairValue(base, growth, years, discount, multiple, margin = 1) {
  return (base * (1 + growth) ** years * margin * multiple) /
    (1 + discount) ** years;
}

function reverseGrowth(price, base, years, discount, multiple, margin = 1) {
  if (![price, base, years, multiple, margin].every((value) => value > 0)) return null;
  return (
    (price * (1 + discount) ** years / (base * margin * multiple)) ** (1 / years) - 1
  );
}

function getModelConfig() {
  const configs = {
    revenue: {
      title: "Revenue 增长模型",
      historyTitle: "Revenue",
      baseLabel: "当前营收/股",
      base: state.data.valuation_bases.revenue.per_share,
      annualField: "revenue_per_share",
      growthKey: "revenue",
      averageKey: "net_margin",
      averageLabel: "平均净利率",
      multipleLabel: "终值 P/E",
      margin: state.netMargin,
      formula: "Revenue/share × 增长 × 净利率 × 终值 P/E，再以要求回报率折现。",
    },
    earnings: {
      title: "Earnings 增长模型",
      historyTitle: "Diluted EPS",
      baseLabel: "当前 EPS",
      base: state.data.valuation_bases.earnings.per_share,
      annualField: "diluted_eps",
      growthKey: "earnings",
      averageKey: "price_to_earnings",
      averageLabel: "平均 P/E",
      multipleLabel: "终值 P/E",
      margin: 1,
      formula: "EPS × 增长 × 终值 P/E，再以要求回报率折现。",
    },
    free_cash_flow: {
      title: "FCF 增长模型",
      historyTitle: "Free Cash Flow / Share",
      baseLabel: "当前 FCF/股",
      base: state.data.valuation_bases.free_cash_flow.per_share,
      annualField: "free_cash_flow_per_share",
      growthKey: "free_cash_flow",
      averageKey: "price_to_fcf",
      averageLabel: "平均 P/FCF",
      multipleLabel: "终值 P/FCF",
      margin: 1,
      formula: "FCF/share × 增长 × 终值 P/FCF，再以要求回报率折现。",
    },
  };
  return configs[state.model];
}

async function loadStock(symbol) {
  const response = await fetch(`../cache/dcf/${symbol}.json`);
  if (!response.ok) throw new Error(`无法读取 ${symbol} 数据`);
  state.data = await response.json();
  state.symbol = symbol;
  setSuggestedInputs();
  render();
}

function setSuggestedInputs() {
  const data = state.data;
  const averages = data.historical_metrics.averages;
  const growth = data.historical_metrics.growth;
  const configKey = state.model === "free_cash_flow" ? "free_cash_flow" : state.model;
  const historicalGrowth = growth[configKey]?.["3y"];
  if (historicalGrowth != null && historicalGrowth > -0.1 && historicalGrowth < 0.35) {
    state.growthRate = historicalGrowth;
  } else {
    state.growthRate = 0.1;
  }
  state.netMargin = averages.net_margin?.["3y"] ?? data.ttm.net_margin ?? 0.2;
  const historicalMultiple = state.model === "free_cash_flow"
    ? averages.price_to_fcf?.["3y"]
    : averages.price_to_earnings?.["3y"];
  state.terminalMultiple = Math.max(5, Math.min(50, Math.round(historicalMultiple ?? 25)));
  syncControls();
}

function syncControls() {
  $("growthRate").value = (state.growthRate * 100).toFixed(1);
  $("netMargin").value = (state.netMargin * 100).toFixed(1);
  $("terminalMultiple").value = state.terminalMultiple;
  $("discountRate").value = (state.discountRate * 100).toFixed(1);
  $("growthOutput").textContent = percent(state.growthRate);
  $("marginOutput").textContent = percent(state.netMargin);
  $("multipleOutput").textContent = `${state.terminalMultiple.toFixed(0)}×`;
  $("discountOutput").textContent = percent(state.discountRate);
}

function render() {
  const data = state.data;
  const config = getModelConfig();
  const currency = data.currency;
  const price = data.market_data.price;
  const base = config.base;
  const futureMetric = base * (1 + state.growthRate) ** state.years;
  const futurePrice = futureMetric * config.margin * state.terminalMultiple;
  const fairValue = forwardFairValue(
    base,
    state.growthRate,
    state.years,
    state.discountRate,
    state.terminalMultiple,
    config.margin,
  );
  const impliedGrowth = reverseGrowth(
    price,
    base,
    state.years,
    state.discountRate,
    state.terminalMultiple,
    config.margin,
  );
  const result = state.direction === "forward" ? fairValue : impliedGrowth;
  const gap = fairValue / price - 1;
  const irr = (futurePrice / price) ** (1 / state.years) - 1;

  $("companyLogo").textContent = data.name.slice(0, 1).toUpperCase();
  $("companyName").textContent = data.name;
  $("companySymbol").textContent = data.symbol;
  $("companyExchange").textContent = data.exchange;
  $("companyIndexes").textContent = data.indexes.map((item) => item.toUpperCase()).join(" · ");
  $("currentPrice").textContent = money(price, currency);
  $("priceDate").textContent = `截至 ${data.market_data.as_of}`;
  $("dataSource").textContent = data.sources.join(" + ").toUpperCase();
  $("lastUpdated").textContent = `数据更新于 ${data.fetched_at.slice(0, 10)}`;

  $("assumptionTitle").textContent = config.title;
  $("baseMetricLabel").textContent = config.baseLabel;
  $("historyTitle").textContent = config.historyTitle;
  $("growthLabel").textContent = `${config.historyTitle} 年增长率`;
  $("multipleLabel").textContent = config.multipleLabel;
  $("marginControl").classList.toggle("hidden", state.model !== "revenue");
  $("formulaText").textContent = config.formula;

  if (state.direction === "forward") {
    $("resultLabel").textContent = "估算内在价值";
    $("resultCurrency").textContent = new Intl.NumberFormat("zh-CN", {
      style: "currency", currency, currencyDisplay: "narrowSymbol",
      minimumFractionDigits: 0, maximumFractionDigits: 0,
    }).formatToParts(0).find((part) => part.type === "currency")?.value ?? "";
    $("primaryResult").textContent = fairValue.toFixed(2);
    $("valuationGap").textContent = percent(gap);
    $("valuationBadge").classList.toggle("positive", gap >= 0);
  } else {
    $("resultLabel").textContent = "市场隐含复合增长率";
    $("resultCurrency").textContent = "";
    $("primaryResult").textContent = impliedGrowth == null ? "—" : percent(impliedGrowth);
    $("valuationGap").textContent = impliedGrowth == null
      ? "基础指标不可用"
      : `未来 ${state.years} 年`;
    $("valuationBadge").classList.toggle("positive", impliedGrowth != null && impliedGrowth <= 0.15);
  }

  $("basePerShare").textContent = money(base, currency);
  $("resultCurrentPrice").textContent = money(price, currency);
  $("forecastIrr").textContent = percent(irr);
  $("basePeriod").textContent =
    data.valuation_bases[state.model === "free_cash_flow" ? "free_cash_flow" : state.model].period.toUpperCase();

  renderHistory(config);
  syncControls();
}

function renderHistory(config) {
  const metrics = state.data.historical_metrics;
  const growth = metrics.growth[config.growthKey];
  const observedPeriods = state.data.annual.filter(
    (row) => row[config.annualField] != null,
  ).length;
  const available = metrics.available_growth_windows?.[config.growthKey]
    ?? [1, 3, 5, 10].filter((years) => observedPeriods > years);
  $("growthChips").innerHTML = [1, 3, 5, 10].map((years) => `
    <div class="growth-chip ${available.includes(years) ? "" : "unavailable"}">
      <span>${years} 年 CAGR</span>
      <strong>${available.includes(years) ? percent(growth[`${years}y`]) : "暂无"}</strong>
    </div>
  `).join("");

  const rows = state.data.annual.slice().reverse().filter((row) => row[config.annualField] != null);
  const values = rows.map((row) => row[config.annualField]);
  const maxValue = Math.max(...values.map(Math.abs), 1);
  $("historyChart").innerHTML = rows.map((row) => {
    const value = row[config.annualField];
    const height = Math.max(4, Math.abs(value) / maxValue * 155);
    return `
      <div class="chart-column">
        <strong>${state.model === "revenue" ? compact(value, state.data.currency) : value.toFixed(2)}</strong>
        <div class="chart-bar" style="height:${height}px;opacity:${value < 0 ? .35 : 1}"></div>
        <span>${row.fiscal_year.slice(0, 4)}</span>
      </div>`;
  }).join("");

  const average = metrics.averages[config.averageKey]?.["3y"];
  $("averageMetricLabel").textContent = config.averageLabel;
  $("averageMetric").textContent = average == null
    ? "—"
    : config.averageKey === "net_margin" ? percent(average) : `${average.toFixed(1)}×`;
  $("availableHistory").textContent = `${Math.max(...available, 0)} 年`;
  $("dataWarning").textContent = available.includes(5)
    ? "历史覆盖已达到 5 年以上，可结合长期区间判断假设。"
    : "当前免费源历史不足 5 年；系统不会推算或补造缺失年份。";
}

function bindEvents() {
  $("stockSelect").addEventListener("change", (event) => loadStock(event.target.value));
  $("directionTabs").addEventListener("click", (event) => {
    if (!event.target.dataset.direction) return;
    state.direction = event.target.dataset.direction;
    document.querySelectorAll("#directionTabs button").forEach((button) =>
      button.classList.toggle("active", button.dataset.direction === state.direction));
    render();
  });
  $("modelTabs").addEventListener("click", (event) => {
    if (!event.target.dataset.model) return;
    state.model = event.target.dataset.model;
    document.querySelectorAll("#modelTabs button").forEach((button) =>
      button.classList.toggle("active", button.dataset.model === state.model));
    setSuggestedInputs();
    render();
  });
  $("periodTabs").addEventListener("click", (event) => {
    if (!event.target.dataset.years) return;
    state.years = Number(event.target.dataset.years);
    document.querySelectorAll("#periodTabs button").forEach((button) =>
      button.classList.toggle("active", Number(button.dataset.years) === state.years));
    render();
  });

  [
    ["growthRate", "growthRate", 100],
    ["netMargin", "netMargin", 100],
    ["terminalMultiple", "terminalMultiple", 1],
    ["discountRate", "discountRate", 100],
  ].forEach(([id, key, divisor]) => {
    $(id).addEventListener("input", (event) => {
      state[key] = Number(event.target.value) / divisor;
      render();
    });
  });

  $("resetButton").addEventListener("click", () => {
    state.discountRate = 0.12;
    state.years = 10;
    document.querySelectorAll("#periodTabs button").forEach((button) =>
      button.classList.toggle("active", Number(button.dataset.years) === 10));
    setSuggestedInputs();
    render();
  });
}

bindEvents();
loadStock(state.symbol).catch((error) => {
  document.body.innerHTML = `<main><h1>数据加载失败</h1><p>${error.message}</p></main>`;
});
