# Deployment Strategy

## Recommended Path

For the mini-program, use Cloudflare Worker as the public data API and keep GitHub
as the versioned JSON store:

```text
GitHub Actions -> cache/*.json in GitHub -> Cloudflare Worker -> mini-program
```

The Worker gives the app a stable domain, CORS control, CDN caching, simple
versioned routes, and room for future fallbacks to R2/KV without changing the
mini-program.

Directly linking the mini-program to GitHub raw files is possible for testing, but
it couples the app to GitHub URL shape, rate behavior, and availability. It also
makes later fallback logic harder.

## Web App

A public Cloudflare Pages site is optional right now. Build it when one of these
is true:

- You want a shareable browser version of the calculator.
- You want SEO, public documentation, or a landing page.
- You want desktop users to test assumptions before the mini-program UI is ready.

The current `web/` prototype can later become that Pages site. It should read the
same Worker API as the mini-program, while all DCF calculations remain local in the
browser or mini-program.

## Data API Contract

Initial routes:

```text
GET /health
GET /manifest
GET /dcf/:symbol
```

The Worker currently proxies GitHub raw JSON and adds cache/CORS headers. If GitHub
becomes too slow or rate-limited, the same routes can be backed by Cloudflare R2 or
KV without changing frontend callers.
