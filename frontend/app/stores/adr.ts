import {
  createAdr,
  fetchAdr,
  fetchAdrReviewStatus,
  listAdrs,
  publishAdr,
  searchAdrs,
  submitAdrForReview,
  updateAdr,
  type AdrResponse,
  type AdrSummary,
  type ReviewAnnotation,
  type ReviewError,
} from "../../composables/useApi";

export type { ReviewAnnotation, ReviewError };

export type Adr = {
  id: string;
  title: string;
  content: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  reviewAnnotations: ReviewAnnotation[] | null;
  reviewedAt: string | null;
  reviewError: ReviewError | null;
};

export type AdrListItem = {
  id: string;
  title: string;
  status: string;
  updatedAt: string;
};

function toAdr(response: AdrResponse): Adr {
  return {
    id: response.id,
    title: response.title,
    content: response.content,
    status: response.status,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
    reviewAnnotations: response.review_annotations ?? null,
    reviewedAt: response.reviewed_at ?? null,
    reviewError: response.review_error ?? null,
  };
}

function toAdrListItem(summary: AdrSummary): AdrListItem {
  return {
    id: summary.id,
    title: summary.title,
    status: summary.status,
    updatedAt: summary.updated_at,
  };
}

export const useAdrStore = defineStore("adr", () => {
  const currentAdr = ref<Adr | null>(null);
  const adrs = ref<AdrListItem[]>([]);
  const loading = ref(false);
  const listLoading = ref(false);
  const listError = ref<string | null>(null);
  const isDirty = ref(false);
  const lastSavedTitle = ref("");
  const lastSavedContent = ref("");

  function syncSavedBaseline() {
    if (!currentAdr.value) {
      lastSavedTitle.value = "";
      lastSavedContent.value = "";
      isDirty.value = false;
      return;
    }
    lastSavedTitle.value = currentAdr.value.title;
    lastSavedContent.value = currentAdr.value.content;
    isDirty.value = false;
  }

  function recomputeDirty() {
    if (!currentAdr.value) {
      isDirty.value = false;
      return;
    }
    isDirty.value =
      currentAdr.value.title !== lastSavedTitle.value ||
      currentAdr.value.content !== lastSavedContent.value;
  }

  function updateTitle(title: string) {
    if (!currentAdr.value) {
      return;
    }
    currentAdr.value = { ...currentAdr.value, title };
    recomputeDirty();
  }

  function updateContent(content: string) {
    if (!currentAdr.value) {
      return;
    }
    currentAdr.value = { ...currentAdr.value, content };
    recomputeDirty();
  }

  async function create(title: string): Promise<void> {
    loading.value = true;
    try {
      const { id } = await createAdr(title);
      await load(id);
      await navigateTo(`/workspace/adr/${id}`);
    } finally {
      loading.value = false;
    }
  }

  async function load(id: string): Promise<void> {
    loading.value = true;
    try {
      const response = await fetchAdr(id);
      currentAdr.value = toAdr(response);
      syncSavedBaseline();
    } finally {
      loading.value = false;
    }
  }

  async function save(): Promise<void> {
    if (!currentAdr.value || !isDirty.value) {
      return;
    }

    const savedAdrId = currentAdr.value.id;
    const savedTitle = currentAdr.value.title;
    const savedContent = currentAdr.value.content;

    loading.value = true;
    try {
      const response = await updateAdr(savedAdrId, {
        title: savedTitle,
        content: savedContent,
      });

      if (
        currentAdr.value &&
        currentAdr.value.id === savedAdrId &&
        currentAdr.value.title === savedTitle &&
        currentAdr.value.content === savedContent
      ) {
        currentAdr.value = toAdr(response);
        syncSavedBaseline();
        return;
      }

      lastSavedTitle.value = savedTitle;
      lastSavedContent.value = savedContent;
      recomputeDirty();
    } finally {
      loading.value = false;
    }
  }

  async function searchByTitle(query: string): Promise<AdrSummary[]> {
    const response = await searchAdrs(query);
    return response.results;
  }

  async function fetchList(): Promise<void> {
    listLoading.value = true;
    listError.value = null;
    try {
      const response = await listAdrs();
      adrs.value = response.results.map(toAdrListItem);
    } catch {
      adrs.value = [];
      listError.value = "Failed to load ADR history";
    } finally {
      listLoading.value = false;
    }
  }

  async function submitForReview(id: string): Promise<void> {
    loading.value = true;
    try {
      await submitAdrForReview(id);
      await load(id);
    } finally {
      loading.value = false;
    }
  }

  async function publish(id: string): Promise<void> {
    loading.value = true;
    try {
      await publishAdr(id);
      await load(id);
    } finally {
      loading.value = false;
    }
  }

  async function refreshReviewStatus(id: string): Promise<void> {
    const status = await fetchAdrReviewStatus(id);
    if (!currentAdr.value || currentAdr.value.id !== id) {
      return;
    }
    currentAdr.value = {
      ...currentAdr.value,
      status: status.status,
      reviewedAt: status.reviewed_at ?? null,
      reviewError: status.review_error ?? null,
    };
  }

  return {
    currentAdr,
    adrs,
    loading,
    listLoading,
    listError,
    isDirty,
    create,
    fetchList,
    load,
    save,
    searchByTitle,
    submitForReview,
    publish,
    refreshReviewStatus,
    updateTitle,
    updateContent,
  };
});
