# Historical Data Strategy

## Stock Investor IQ

The referenced calculator is delivered through a public Power BI embed. Its browser
can retrieve report data, but those internal Power BI requests are not a documented
data API. They depend on transient report metadata and a proprietary semantic model.

The site's Terms of Use also prohibit automated access, systematic retrieval, data
mining, reverse engineering, and building a database from its content. The project
therefore does not scrape or redistribute that report. It may be used manually as a
comparison tool, not as a production dependency.

## Five- and Ten-Year History

Source priority by market:

1. US: SEC Company Facts, up to 12 annual periods, with yfinance as fallback.
2. China A shares: yfinance for the current prototype; exchange/CNINFO annual filings
   are the preferred future source for longer history.
3. Hong Kong: yfinance for the current prototype; HKEX/company annual reports are the
   preferred future source for longer history.

For US data, create `.env` locally from `.env.example`, or add a GitHub Actions
secret named `SEC_USER_AGENT`. SEC currently rejects anonymous/generic requests,
so the project cannot pull the 12-year layer until that value is provided by the
operator.

## A/H Share Options

Open-source code exists, but a clean redistributable dataset is harder:

- AKShare: useful MIT-licensed Python collector for A-share and Hong Kong market
  data. Treat it as a collector, not a license grant for redistributing upstream
  website data.
- Tushare: broad China fundamentals coverage, but token/points and service terms
  make it closer to a hosted API dependency than an open dataset.
- CNINFO/SSE/SZSE/HKEX/company annual reports: best long-term factual source, but
  parsing is more work, especially for hundreds of companies.

Recommended path: keep yfinance for A/H prototype coverage, then add an optional
`akshare` collector behind a source flag for fields where redistribution is acceptable.
For high-conviction portfolio names, prefer official annual reports or exchange filings.

Each stock JSON publishes `historical_metrics.available_growth_windows`. The frontend
must only enable 1-, 3-, 5-, or 10-year controls when the corresponding window exists.
Missing history stays unavailable rather than being estimated from unrelated data.

## Share Count and Per-Share Metrics

Share count is a first-class data field because DCF output is ultimately a per-share
value.

- Current TTM per-share bases use latest available shares outstanding:
  `TTM revenue / current shares` and `TTM free cash flow / current shares`.
- Historical annual per-share metrics use each fiscal year's diluted weighted average
  shares where available, so buybacks, dilution, and issuance are reflected in the
  historical trend.
- Market cap and enterprise value are recalculated whenever price or current shares
  change.
- Annual diluted shares are retained by fiscal year and should not be overwritten by
  a shorter upstream response.

For the calculator UI, label current per-share fields as current bases, and label
annual chart fields as historical diluted per-share metrics.

## Other Options

- A licensed fundamentals API is the lowest-maintenance option for full global
  10-year coverage.
- Annual-report extraction is appropriate for a smaller curated portfolio, but is
  expensive for hundreds of companies.
- Storing each newly reported fiscal year creates a durable internal history going
  forward, even when an upstream free API later shortens its history.

## Long-Term DCF Guardrails

Long-running valuation data should protect against these drift risks:

- Currency: price, revenue, FCF, cash, debt, and per-share metrics must keep their
  source currency. Cross-listed stocks and ADRs should not be mixed without an FX
  conversion layer.
- Share count: current shares are for current market cap and TTM bases; annual
  diluted shares are for historical per-share trends.
- Splits and corporate actions: price history from yfinance is adjusted enough for
  current prototype ratios, but current shares should still be refreshed after split,
  buyback, issuance, or major stock compensation events.
- Negative or cyclical FCF: reverse DCF should block or clearly label calculations
  when the base metric is negative, near zero, or not economically meaningful.
- Missing years: do not interpolate financial history by default. Expose available
  windows and let the UI disable 5-year or 10-year views when real data is missing.
- Restatements: newer SEC/company facts should overwrite the same fiscal year, but
  older snapshots remain archived for audit.
- Index membership: current index constituents are refreshed; historical membership
  is not yet modeled, so backtests should not treat today's universe as a historical
  index portfolio.
- Financial company metrics: banks, insurers, brokers, and asset managers may need
  separate valuation models because debt, cash flow, and enterprise value behave
  differently from industrial companies.
