import { getRequestURL, proxyRequest } from "h3";

/**
 * Same-origin /api/* proxy with runtime upstream (NUXT_API_UPSTREAM).
 * Preserves the /api prefix so the backend and frontend expose one API contract.
 */
export default defineEventHandler(async (event) => {
  const { apiUpstream } = useRuntimeConfig(event);
  const upstream = apiUpstream.replace(/\/$/, "");
  const url = getRequestURL(event);
  const target = `${upstream}${url.pathname}${url.search}`;

  return proxyRequest(event, target);
});
