import { useEventListener } from "@vueuse/core";
import { apiPath } from "../../composables/useApi";
import type { useAdrStore } from "../stores/adr";

const BEACON_PAYLOAD_WARNING_BYTES = 60 * 1024;

export function useAdrPersistence(
  adrId: Ref<string>,
  store: ReturnType<typeof useAdrStore>,
  isSubmitting?: Ref<boolean>,
) {
  const isReviewEditable = computed(
    () =>
      store.currentAdr?.status !== "in_review" &&
      !(isSubmitting?.value ?? false),
  );

  async function saveOnBlur() {
    if (!isReviewEditable.value || !store.isDirty) {
      return;
    }
    await store.save();
  }

  function beaconSave() {
    if (!isReviewEditable.value || !store.isDirty || !store.currentAdr) {
      return;
    }

    const blob = createSaveBlob(store.currentAdr);
    const url = apiPath(`/adrs/${adrId.value}/save`);
    const queued = navigator.sendBeacon?.(url, blob) ?? false;

    if (!queued) {
      void fetch(url, {
        method: "POST",
        body: blob,
        keepalive: true,
        credentials: "include",
      }).catch(() => undefined);
    }
  }

  function createSaveBlob(adr: { title: string; content: string }) {
    const payload = JSON.stringify({
      title: adr.title,
      content: adr.content,
    });
    return new Blob([payload], { type: "application/json" });
  }

  function warnIfBeaconIsRisky(event: BeforeUnloadEvent) {
    if (!isReviewEditable.value || !store.isDirty || !store.currentAdr) {
      return;
    }

    if (
      typeof navigator.sendBeacon === "function" &&
      createSaveBlob(store.currentAdr).size <= BEACON_PAYLOAD_WARNING_BYTES
    ) {
      return;
    }

    event.preventDefault();
    event.returnValue = "";
  }

  if (import.meta.client) {
    useEventListener(window, "beforeunload", warnIfBeaconIsRisky);
    useEventListener(window, "pagehide", beaconSave);
    useEventListener(document, "visibilitychange", () => {
      if (document.visibilityState === "hidden") {
        beaconSave();
      }
    });
  }

  return {
    saveOnBlur,
    isReviewEditable,
  };
}
