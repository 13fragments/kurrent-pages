// Serves the static site on kurrentpages.org and sends every other host
// (www, kurrentpages.com) and plain HTTP there with a permanent redirect.
const CANONICAL_HOST = "kurrentpages.org";
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1"]);

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (LOCAL_HOSTS.has(url.hostname)) return env.ASSETS.fetch(request);
    if (url.hostname !== CANONICAL_HOST || url.protocol !== "https:") {
      url.protocol = "https:";
      url.hostname = CANONICAL_HOST;
      url.port = "";
      return Response.redirect(url.toString(), 301);
    }
    return env.ASSETS.fetch(request);
  },
};
