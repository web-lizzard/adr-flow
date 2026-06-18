export type HealthResponse = {
  status: string;
};

export type ReviewAnnotationKind =
  | "missing_section"
  | "inconsistency"
  | "conciseness";

export type ReviewAnnotation = {
  kind: ReviewAnnotationKind;
  message: string;
  location?: string | null;
  suggestion?: string | null;
};

export type ReviewError = {
  source_event_id: string;
  code: string;
  message: string;
  failed_at: string;
};

export type AdrResponse = {
  id: string;
  title: string;
  content: string;
  status: string;
  created_at: string;
  updated_at: string;
  review_annotations?: ReviewAnnotation[] | null;
  reviewed_at?: string | null;
  review_error?: ReviewError | null;
};

export type ReviewStatusResponse = {
  status: string;
  reviewed_at?: string | null;
  review_error?: ReviewError | null;
  annotation_counts?: Record<string, number> | null;
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

export type ListAdrsResponse = {
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

export function listAdrs() {
  return $fetch<ListAdrsResponse>(apiPath("/adrs"));
}

export function submitAdrForReview(id: string) {
  return $fetch<void>(apiPath(`/adrs/${id}/submit-review`), {
    method: "POST",
  });
}

export function publishAdr(id: string) {
  return $fetch<void>(apiPath(`/adrs/${id}/publish`), {
    method: "POST",
  });
}

export function fetchAdrReviewStatus(id: string) {
  return $fetch<ReviewStatusResponse>(apiPath(`/adrs/${id}/review-status`));
}
