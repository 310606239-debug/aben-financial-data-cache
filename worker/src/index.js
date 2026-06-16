const DEFAULT_REPO_RAW_BASE =
  "https://raw.githubusercontent.com/310606239-debug/aben-financial-data-cache/main";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const JSON_HEADERS = {
  ...CORS_HEADERS,
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400",
};

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: JSON_HEADERS,
  });
}

function normalizeSymbol(symbol) {
  return symbol.trim().toUpperCase();
}

function upstreamUrl(env, path) {
  const base = (env.REPO_RAW_BASE || DEFAULT_REPO_RAW_BASE).replace(/\/$/, "");
  return `${base}${path}`;
}

async function proxyJson(request, env, path) {
  const upstream = upstreamUrl(env, path);
  const response = await fetch(upstream, {
    headers: {
      Accept: "application/json",
      "User-Agent": "aben-financial-data-cache-worker",
    },
    cf: {
      cacheEverything: true,
      cacheTtl: path.includes("/dcf/") ? 3600 : 600,
    },
  });

  if (!response.ok) {
    return jsonResponse({
      error: "upstream_error",
      status: response.status,
      upstream,
    }, response.status === 404 ? 404 : 502);
  }

  return new Response(response.body, {
    status: response.status,
    headers: JSON_HEADERS,
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      return jsonResponse({ error: "method_not_allowed" }, 405);
    }

    if (url.pathname === "/" || url.pathname === "/health") {
      return jsonResponse({
        ok: true,
        service: "aben-financial-data-cache",
        routes: ["/manifest", "/dcf/:symbol"],
      });
    }

    if (url.pathname === "/manifest") {
      return proxyJson(request, env, "/cache/manifest.json");
    }

    const dcfMatch = url.pathname.match(/^\/dcf\/([A-Za-z0-9.\-]+)$/);
    if (dcfMatch) {
      const symbol = normalizeSymbol(dcfMatch[1]);
      return proxyJson(request, env, `/cache/dcf/${symbol}.json`);
    }

    return jsonResponse({ error: "not_found" }, 404);
  },
};
