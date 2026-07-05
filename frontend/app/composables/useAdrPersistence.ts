import { useEventListener } from "@vueuse/core";
import { apiPath } from "../../composables/useApi";
import { getAccessToken } from "../../composables/useAuthToken";
import type { useAdrStore } from "../stores/adr";

const BEACON_PAYLOAD_WARNING_BYTES = 60 * 1024;

function isClient(): boolean {
  return typeof window !== "undefined" && import.meta.client !== false;
}

export function useAdrPersistence(
  adrId: Ref<string>,
  store: ReturnType<typeof useAdrStore>,
  isBlockingSave?: Ref<boolean>,
) {
  const isReviewEditable = computed(
    () =>
      store.currentAdr?.status !== "in_review" &&
      !(isBlockingSave?.value ?? false),
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

    const token = getAccessToken();
    if (!token) {
      return;
    }

    const blob = createSaveBlob(store.currentAdr);
    const url = apiPath(`/adrs/${adrId.value}/save`);

    void fetch(url, {
      method: "POST",
      body: blob,
      keepalive: true,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    }).catch(() => undefined);
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

    if (createSaveBlob(store.currentAdr).size <= BEACON_PAYLOAD_WARNING_BYTES) {
      return;
    }

    event.preventDefault();
    event.returnValue = "";
  }

  if (isClient()) {
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
