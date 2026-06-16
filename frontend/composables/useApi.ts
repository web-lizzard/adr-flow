export type HealthResponse = {
  status: string;
};

export type AdrResponse = {
  id: string;
  title: string;
  content: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type CreateAdrResponse = {
  id: string;
};

export type AdrSummary = {
  id: string;
  title: string;
  status: string;
  updated_at: string;
};

export type SearchAdrsResponse = {
  results: AdrSummary[];
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

export function createAdr(title: string) {
  return $fetch<CreateAdrResponse>(apiPath("/adrs"), {
    method: "POST",
    body: { title },
  });
}

export function fetchAdr(id: string) {
  return $fetch<AdrResponse>(apiPath(`/adrs/${id}`));
}

export function updateAdr(
  id: string,
  data: { title?: string; content?: string },
) {
  return $fetch<AdrResponse>(apiPath(`/adrs/${id}`), {
    method: "PATCH",
    body: data,
  });
}

export function searchAdrs(query: string) {
  return $fetch<SearchAdrsResponse>(apiPath("/adrs/search"), {
    query: { q: query },
  });
}
