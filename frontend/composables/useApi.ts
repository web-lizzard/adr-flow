export type HealthResponse = {
  status: string;
};

/** Build a same-origin API path (e.g. `/api/health`). */
export function apiPath(segment: string): string {
  const base = useRuntimeConfig().public.apiBase.replace(/\/$/, "");
  const path = segment.startsWith("/") ? segment : `/${segment}`;
  return `${base}${path}`;
}

export function fetchHealth() {
  return $fetch<HealthResponse>(apiPath("/health"));
}
