import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useAdrStore } from "../app/stores/adr";

const createAdrMock = vi.fn();
const fetchAdrMock = vi.fn();
const updateAdrMock = vi.fn();
const searchAdrsMock = vi.fn();
const listAdrsMock = vi.fn();
const submitAdrForReviewMock = vi.fn();
const publishAdrMock = vi.fn();
const fetchAdrReviewStatusMock = vi.fn();

vi.mock("../composables/useApi", () => ({
  createAdr: (...args: unknown[]) => createAdrMock(...args),
  fetchAdr: (...args: unknown[]) => fetchAdrMock(...args),
  updateAdr: (...args: unknown[]) => updateAdrMock(...args),
  searchAdrs: (...args: unknown[]) => searchAdrsMock(...args),
  listAdrs: (...args: unknown[]) => listAdrsMock(...args),
  submitAdrForReview: (...args: unknown[]) => submitAdrForReviewMock(...args),
  publishAdr: (...args: unknown[]) => publishAdrMock(...args),
  fetchAdrReviewStatus: (...args: unknown[]) =>
    fetchAdrReviewStatusMock(...args),
}));

const navigateToMock = vi.fn();
vi.stubGlobal("navigateTo", navigateToMock);

const sampleAdr = {
  id: "adr-1",
  title: "My ADR",
  content: "## Context\n\n## Options",
  status: "draft",
  created_at: "2026-06-16T10:00:00Z",
  updated_at: "2026-06-16T10:00:00Z",
};

describe("useAdrStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    createAdrMock.mockReset();
    fetchAdrMock.mockReset();
    updateAdrMock.mockReset();
    searchAdrsMock.mockReset();
    listAdrsMock.mockReset();
    submitAdrForReviewMock.mockReset();
    publishAdrMock.mockReset();
    fetchAdrReviewStatusMock.mockReset();
    navigateToMock.mockReset();
  });

  it("create(title) calls POST /api/adrs with title and sets currentAdr", async () => {
    createAdrMock.mockResolvedValue({ id: "adr-1" });
    fetchAdrMock.mockResolvedValue(sampleAdr);

    const store = useAdrStore();
    await store.create("My ADR");

    expect(createAdrMock).toHaveBeenCalledWith("My ADR");
    expect(fetchAdrMock).toHaveBeenCalledWith("adr-1");
    expect(store.currentAdr).toEqual({
      id: "adr-1",
      title: "My ADR",
      content: "## Context\n\n## Options",
      status: "draft",
      createdAt: "2026-06-16T10:00:00Z",
      updatedAt: "2026-06-16T10:00:00Z",
      reviewAnnotations: null,
      reviewedAt: null,
      reviewError: null,
    });
    expect(store.isDirty).toBe(false);
    expect(navigateToMock).toHaveBeenCalledWith("/workspace/adr/adr-1");
  });

  it("create(title) propagates 409 error for duplicate titles", async () => {
    const conflict = {
      statusCode: 409,
      data: { detail: "Title already exists" },
    };
    createAdrMock.mockRejectedValue(conflict);

    const store = useAdrStore();

    await expect(store.create("Duplicate")).rejects.toEqual(conflict);
    expect(fetchAdrMock).not.toHaveBeenCalled();
    expect(store.currentAdr).toBeNull();
  });

  it("load(id) calls GET /api/adrs/{id} and populates state", async () => {
    fetchAdrMock.mockResolvedValue(sampleAdr);

    const store = useAdrStore();
    await store.load("adr-1");

    expect(fetchAdrMock).toHaveBeenCalledWith("adr-1");
    expect(store.currentAdr?.title).toBe("My ADR");
    expect(store.isDirty).toBe(false);
  });

  it("save() calls PATCH /api/adrs/{id} when dirty", async () => {
    fetchAdrMock.mockResolvedValue(sampleAdr);
    updateAdrMock.mockResolvedValue({
      ...sampleAdr,
      content: "updated content",
      updated_at: "2026-06-16T11:00:00Z",
    });

    const store = useAdrStore();
    await store.load("adr-1");
    store.updateContent("updated content");

    await store.save();

    expect(updateAdrMock).toHaveBeenCalledWith("adr-1", {
      title: "My ADR",
      content: "updated content",
    });
    expect(store.currentAdr?.content).toBe("updated content");
    expect(store.isDirty).toBe(false);
  });

  it("save() skips API call when not dirty", async () => {
    fetchAdrMock.mockResolvedValue(sampleAdr);

    const store = useAdrStore();
    await store.load("adr-1");
    await store.save();

    expect(updateAdrMock).not.toHaveBeenCalled();
  });

  it("save() preserves edits made while a PATCH is in flight", async () => {
    fetchAdrMock.mockResolvedValue(sampleAdr);
    let resolveUpdate: (value: typeof sampleAdr) => void = () => {};
    updateAdrMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveUpdate = resolve;
        }),
    );

    const store = useAdrStore();
    await store.load("adr-1");
    store.updateContent("first edit");

    const savePromise = store.save();
    store.updateContent("second edit");

    resolveUpdate({
      ...sampleAdr,
      content: "first edit",
      updated_at: "2026-06-16T11:00:00Z",
    });
    await savePromise;

    expect(updateAdrMock).toHaveBeenCalledWith("adr-1", {
      title: "My ADR",
      content: "first edit",
    });
    expect(store.currentAdr?.content).toBe("second edit");
    expect(store.isDirty).toBe(true);
  });

  it("searchByTitle(query) calls GET /api/adrs/search and returns results", async () => {
    searchAdrsMock.mockResolvedValue({
      results: [
        {
          id: "adr-1",
          title: "My ADR",
          status: "draft",
          updated_at: "2026-06-16T10:00:00Z",
        },
      ],
    });

    const store = useAdrStore();
    const results = await store.searchByTitle("My");

    expect(searchAdrsMock).toHaveBeenCalledWith("My");
    expect(results).toHaveLength(1);
    expect(results[0]?.title).toBe("My ADR");
  });

  it("fetchList() populates adrs and clears listError on success", async () => {
    listAdrsMock.mockResolvedValue({
      results: [
        {
          id: "adr-2",
          title: "Second ADR",
          status: "proposed",
          updated_at: "2026-06-16T11:00:00Z",
        },
      ],
    });

    const store = useAdrStore();
    await store.fetchList();

    expect(listAdrsMock).toHaveBeenCalledTimes(1);
    expect(store.adrs).toEqual([
      {
        id: "adr-2",
        title: "Second ADR",
        status: "proposed",
        updatedAt: "2026-06-16T11:00:00Z",
      },
    ]);
    expect(store.listError).toBeNull();
    expect(store.listLoading).toBe(false);
  });

  it("fetchList() sets listLoading while request is in flight", async () => {
    let resolveList: (value: {
      results: Array<{
        id: string;
        title: string;
        status: string;
        updated_at: string;
      }>;
    }) => void = () => {};
    listAdrsMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveList = resolve;
        }),
    );

    const store = useAdrStore();
    const fetchPromise = store.fetchList();
    expect(store.listLoading).toBe(true);

    resolveList({ results: [] });
    await fetchPromise;
    expect(store.listLoading).toBe(false);
  });

  it("fetchList() stores a readable error and resets listLoading on failure", async () => {
    listAdrsMock.mockRejectedValue(new Error("Backend unavailable"));

    const store = useAdrStore();
    await store.fetchList();

    expect(store.adrs).toEqual([]);
    expect(store.listError).toBe("Failed to load ADR history");
    expect(store.listLoading).toBe(false);
  });

  it("dirty tracking: changes to content/title set isDirty", async () => {
    fetchAdrMock.mockResolvedValue(sampleAdr);

    const store = useAdrStore();
    await store.load("adr-1");

    expect(store.isDirty).toBe(false);

    store.updateContent("new content");
    expect(store.isDirty).toBe(true);

    store.updateContent(sampleAdr.content);
    expect(store.isDirty).toBe(false);

    store.updateTitle("Renamed ADR");
    expect(store.isDirty).toBe(true);
  });

  it("load(id) maps review annotations, reviewedAt, and reviewError from API", async () => {
    fetchAdrMock.mockResolvedValue({
      ...sampleAdr,
      status: "after_review",
      review_annotations: [
        {
          kind: "missing_section",
          message: "Add a Consequences section",
          location: "## Consequences",
          suggestion: "Describe trade-offs",
        },
      ],
      reviewed_at: "2026-06-16T12:00:00Z",
      review_error: null,
    });

    const store = useAdrStore();
    await store.load("adr-1");

    expect(store.currentAdr?.reviewAnnotations).toEqual([
      {
        kind: "missing_section",
        message: "Add a Consequences section",
        location: "## Consequences",
        suggestion: "Describe trade-offs",
      },
    ]);
    expect(store.currentAdr?.reviewedAt).toBe("2026-06-16T12:00:00Z");
    expect(store.currentAdr?.reviewError).toBeNull();
  });

  it("publish(id) calls publish endpoint and reloads the ADR", async () => {
    fetchAdrMock
      .mockResolvedValueOnce({
        ...sampleAdr,
        status: "after_review",
      })
      .mockResolvedValueOnce({
        ...sampleAdr,
        status: "proposed",
      });
    publishAdrMock.mockResolvedValue(undefined);

    const store = useAdrStore();
    await store.load("adr-1");
    await store.publish("adr-1");

    expect(publishAdrMock).toHaveBeenCalledWith("adr-1");
    expect(fetchAdrMock).toHaveBeenCalledTimes(2);
    expect(store.currentAdr?.status).toBe("proposed");
  });

  it("publish(id) sets loading while request is in flight", async () => {
    fetchAdrMock.mockResolvedValue({ ...sampleAdr, status: "after_review" });
    let resolvePublish: () => void = () => {};
    publishAdrMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolvePublish = resolve;
        }),
    );

    const store = useAdrStore();
    await store.load("adr-1");
    const publishPromise = store.publish("adr-1");
    expect(store.loading).toBe(true);

    resolvePublish();
    await publishPromise;
    expect(store.loading).toBe(false);
  });

  it("submitForReview(id) calls submit-review and reloads the ADR", async () => {
    fetchAdrMock.mockResolvedValueOnce(sampleAdr).mockResolvedValueOnce({
      ...sampleAdr,
      status: "in_review",
      review_annotations: null,
      reviewed_at: null,
      review_error: null,
    });
    submitAdrForReviewMock.mockResolvedValue(undefined);

    const store = useAdrStore();
    await store.load("adr-1");
    await store.submitForReview("adr-1");

    expect(submitAdrForReviewMock).toHaveBeenCalledWith("adr-1");
    expect(fetchAdrMock).toHaveBeenCalledTimes(2);
    expect(store.currentAdr?.status).toBe("in_review");
  });

  it("refreshReviewStatus(id) updates status metadata from review-status endpoint", async () => {
    fetchAdrMock.mockResolvedValue(sampleAdr);
    fetchAdrReviewStatusMock.mockResolvedValue({
      status: "after_review",
      reviewed_at: "2026-06-16T12:00:00Z",
      review_error: null,
      annotation_counts: { missing_section: 1 },
    });

    const store = useAdrStore();
    await store.load("adr-1");
    await store.refreshReviewStatus("adr-1");

    expect(fetchAdrReviewStatusMock).toHaveBeenCalledWith("adr-1");
    expect(store.currentAdr?.status).toBe("after_review");
    expect(store.currentAdr?.reviewedAt).toBe("2026-06-16T12:00:00Z");
  });
});
