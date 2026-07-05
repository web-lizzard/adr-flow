import { getAccessToken } from "./useAuthToken";

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
  kind: string;
};

export type SectionRating = {
  section: string;
  score: number;
  feedback: string;
};

export type AdrResponse = {
  id: string;
  title: string;
  content: string;
  status: string;
  created_at: string;
  updated_at: string;
  review_annotations?: ReviewAnnotation[] | null;
  section_ratings?: SectionRating[] | null;
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

function is401(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    (error as { status?: number }).status === 401
  );
}

function shouldRedirectToLogin(): boolean {
  if (typeof window === "undefined" || import.meta.server === true) {
    return false;
  }
  const path = window.location.pathname;
  return path !== "/login" && path !== "/register";
}

export async function apiFetch<T>(
  url: string,
  options?: Parameters<typeof $fetch>[1],
): Promise<T> {
  const headers: Record<string, string> = {
    ...((options?.headers as Record<string, string> | undefined) ?? {}),
  };
  const token = getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  try {
    return await $fetch<T>(url, { ...options, headers });
  } catch (error) {
    if (is401(error)) {
      const { useAuthStore } = await import("../app/stores/auth");
      useAuthStore().clearAuth();
      if (shouldRedirectToLogin()) {
        await navigateTo("/login");
      }
    }
    throw error;
  }
}

export function fetchHealth() {
  return $fetch<HealthResponse>(apiPath("/health"));
}

export function createAdr(title: string) {
  return apiFetch<CreateAdrResponse>(apiPath("/adrs"), {
    method: "POST",
    body: { title },
  });
}

export function fetchAdr(id: string) {
  return apiFetch<AdrResponse>(apiPath(`/adrs/${id}`));
}

export function updateAdr(
  id: string,
  data: { title?: string; content?: string },
) {
  return apiFetch<AdrResponse>(apiPath(`/adrs/${id}`), {
    method: "PATCH",
    body: data,
  });
}

export function searchAdrs(query: string) {
  return apiFetch<SearchAdrsResponse>(apiPath("/adrs/search"), {
    query: { q: query },
  });
}

export function listAdrs() {
  return apiFetch<ListAdrsResponse>(apiPath("/adrs"));
}

export function submitAdrForReview(id: string) {
  return apiFetch<void>(apiPath(`/adrs/${id}/submit-review`), {
    method: "POST",
  });
}

export function retryAdrForReview(id: string) {
  return apiFetch<void>(apiPath(`/adrs/${id}/retry-review`), {
    method: "POST",
  });
}

export function publishAdr(id: string) {
  return apiFetch<void>(apiPath(`/adrs/${id}/publish`), {
    method: "POST",
  });
}

export function deleteAdr(id: string) {
  return apiFetch<void>(apiPath(`/adrs/${id}`), {
    method: "DELETE",
  });
}

export function fetchAdrReviewStatus(id: string) {
  return apiFetch<ReviewStatusResponse>(apiPath(`/adrs/${id}/review-status`));
}
