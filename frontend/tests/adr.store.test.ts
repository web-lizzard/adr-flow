import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { useAdrStore } from "../app/stores/adr";

const createAdrMock = vi.fn();
const fetchAdrMock = vi.fn();
const updateAdrMock = vi.fn();
const searchAdrsMock = vi.fn();

vi.mock("../composables/useApi", () => ({
  createAdr: (...args: unknown[]) => createAdrMock(...args),
  fetchAdr: (...args: unknown[]) => fetchAdrMock(...args),
  updateAdr: (...args: unknown[]) => updateAdrMock(...args),
  searchAdrs: (...args: unknown[]) => searchAdrsMock(...args),
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
});
