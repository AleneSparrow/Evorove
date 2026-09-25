// evorove.com is one site: the Worker serves the built app and forwards
// /api/* and /widget/* to the engine on Railway, so the browser only ever
// talks to evorove.com (no separate API domain, no CORS).
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/widget/")) {
      const target = new URL(url.pathname + url.search, env.API_ORIGIN);
      return fetch(new Request(target, request), { redirect: "manual" });
    }
    return env.ASSETS.fetch(request);
  },
};
