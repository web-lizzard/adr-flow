import { getRequestURL, proxyRequest } from "h3";

/**
 * Same-origin /api/* proxy with runtime upstream (NUXT_API_UPSTREAM).
 * Strips the /api prefix before forwarding (e.g. /api/health → {upstream}/health).
 */
export default defineEventHandler(async (event) => {
  const { apiUpstream } = useRuntimeConfig(event);
  const upstream = apiUpstream.replace(/\/$/, "");
  const url = getRequestURL(event);
  const path = url.pathname.replace(/^\/api/, "") || "/";
  const target = `${upstream}${path}${url.search}`;

  return proxyRequest(event, target);
});
