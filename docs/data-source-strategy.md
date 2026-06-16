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

## Other Options

- A licensed fundamentals API is the lowest-maintenance option for full global
  10-year coverage.
- Annual-report extraction is appropriate for a smaller curated portfolio, but is
  expensive for hundreds of companies.
- Storing each newly reported fiscal year creates a durable internal history going
  forward, even when an upstream free API later shortens its history.
