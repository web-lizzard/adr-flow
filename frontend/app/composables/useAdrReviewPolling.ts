import { useIntervalFn } from "@vueuse/core";

const POLL_INTERVAL_MS = 3000;
const MAX_CONSECUTIVE_POLL_FAILURES = 3;

function isReviewPending(
  adr: { status: string; reviewError: unknown } | null | undefined,
): boolean {
  return adr?.status === "in_review" && adr.reviewError === null;
}

export function useAdrReviewPolling(
  adrId: Ref<string>,
  adr: ReturnType<typeof useAdr>,
) {
  const isPolling = ref(false);
  const pollError = ref<string | null>(null);
  let consecutiveFailures = 0;
  let inFlight = false;

  const { pause, resume } = useIntervalFn(
    async () => {
      if (inFlight) {
        return;
      }

      if (!isReviewPending(adr.currentAdr.value)) {
        pause();
        isPolling.value = false;
        return;
      }

      const previousStatus = adr.currentAdr.value!.status;
      const hadReviewError = adr.currentAdr.value!.reviewError;

      inFlight = true;
      try {
        await adr.refreshReviewStatus(adrId.value);
        consecutiveFailures = 0;
        pollError.value = null;
      } catch {
        consecutiveFailures += 1;
        if (consecutiveFailures >= MAX_CONSECUTIVE_POLL_FAILURES) {
          pause();
          isPolling.value = false;
          pollError.value =
            "Unable to check review status. Refresh the page to try again.";
          return;
        }
        pollError.value = "Failed to check review status. We'll keep trying.";
        return;
      } finally {
        inFlight = false;
      }

      const updated = adr.currentAdr.value;
      if (!updated) {
        pause();
        isPolling.value = false;
        return;
      }

      if (updated.status !== previousStatus) {
        pause();
        isPolling.value = false;
        if (updated.status === "after_review") {
          await adr.load(adrId.value);
        }
        return;
      }

      if (!hadReviewError && updated.reviewError) {
        pause();
        isPolling.value = false;
      }
    },
    POLL_INTERVAL_MS,
    { immediate: false },
  );

  function stopPolling() {
    pause();
    isPolling.value = false;
  }

  watch(
    () => isReviewPending(adr.currentAdr.value),
    (shouldPoll) => {
      if (shouldPoll) {
        consecutiveFailures = 0;
        pollError.value = null;
        isPolling.value = true;
        resume();
        return;
      }
      stopPolling();
    },
    { immediate: true },
  );

  onUnmounted(() => {
    stopPolling();
  });

  return {
    isPolling: computed(() => isPolling.value),
    pollError: computed(() => pollError.value),
  };
}
