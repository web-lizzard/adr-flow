import { computed, onUnmounted, ref, watch } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAdrReviewPolling } from "../app/composables/useAdrReviewPolling";

vi.stubGlobal("watch", watch);
vi.stubGlobal("onUnmounted", onUnmounted);
vi.stubGlobal("computed", computed);
vi.stubGlobal("ref", ref);

const pauseMock = vi.fn();
const resumeMock = vi.fn();
let pollTick: (() => Promise<void>) | null = null;

vi.mock("@vueuse/core", () => ({
  useIntervalFn: (fn: () => Promise<void>) => {
    pollTick = fn;
    return { pause: pauseMock, resume: resumeMock };
  },
}));

function createAdrStub(overrides: Record<string, unknown> = {}) {
  const currentAdr = ref({
    id: "adr-1",
    title: "ADR",
    content: "## Context",
    status: "in_review",
    createdAt: "2026-06-16T10:00:00Z",
    updatedAt: "2026-06-16T10:00:00Z",
    reviewAnnotations: null,
    reviewedAt: null,
    reviewError: null,
    ...overrides,
  });

  const refreshReviewStatus = vi.fn(async () => {
    if (currentAdr.value) {
      currentAdr.value = { ...currentAdr.value };
    }
  });
  const load = vi.fn().mockResolvedValue(undefined);

  const adr = {
    currentAdr: computed(() => currentAdr.value),
    refreshReviewStatus,
    load,
  };

  return { currentAdr, adr, refreshReviewStatus, load };
}

describe("useAdrReviewPolling", () => {
  beforeEach(() => {
    pauseMock.mockClear();
    resumeMock.mockClear();
    pollTick = null;
  });

  it("does not start polling when in_review already has review_error", () => {
    const { adr } = createAdrStub({
      reviewError: {
        source_event_id: "evt-1",
        code: "validation_failed",
        message: "Review output was invalid",
        failed_at: "2026-06-16T12:00:00Z",
      },
    });
    const adrId = ref("adr-1");

    const { isPolling } = useAdrReviewPolling(adrId, adr as never);

    expect(isPolling.value).toBe(false);
    expect(resumeMock).not.toHaveBeenCalled();
  });

  it("stops polling after refreshReviewStatus returns review_error", async () => {
    const { adr, currentAdr, refreshReviewStatus } = createAdrStub();
    const adrId = ref("adr-1");

    refreshReviewStatus.mockImplementation(async () => {
      currentAdr.value = {
        ...currentAdr.value,
        reviewError: {
          source_event_id: "evt-1",
          code: "validation_failed",
          message: "Review output was invalid",
          failed_at: "2026-06-16T12:00:00Z",
        },
      };
    });

    const { isPolling } = useAdrReviewPolling(adrId, adr as never);
    expect(isPolling.value).toBe(true);

    await pollTick?.();

    expect(isPolling.value).toBe(false);
    expect(pauseMock).toHaveBeenCalled();
  });

  it("stops polling after repeated refreshReviewStatus failures", async () => {
    const { adr, refreshReviewStatus } = createAdrStub();
    const adrId = ref("adr-1");

    refreshReviewStatus.mockRejectedValue(new Error("network"));

    const { isPolling, pollError } = useAdrReviewPolling(adrId, adr as never);
    expect(isPolling.value).toBe(true);

    await pollTick?.();
    expect(pollError.value).toContain("keep trying");

    await pollTick?.();
    await pollTick?.();

    expect(isPolling.value).toBe(false);
    expect(pollError.value).toContain("Refresh the page");
    expect(pauseMock).toHaveBeenCalled();
  });
});
