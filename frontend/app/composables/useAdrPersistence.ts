import { useEventListener } from "@vueuse/core";
import { apiPath } from "../../composables/useApi";
import type { useAdrStore } from "../stores/adr";

export function useAdrPersistence(
  adrId: Ref<string>,
  store: ReturnType<typeof useAdrStore>,
) {
  async function saveOnBlur() {
    if (store.isDirty) {
      await store.save();
    }
  }

  function beaconSave() {
    if (!store.isDirty || !store.currentAdr) {
      return;
    }

    const payload = JSON.stringify({
      title: store.currentAdr.title,
      content: store.currentAdr.content,
    });
    const blob = new Blob([payload], { type: "application/json" });
    navigator.sendBeacon(apiPath(`/adrs/${adrId.value}/save`), blob);
  }

  useEventListener(window, "pagehide", beaconSave);
  useEventListener(document, "visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      beaconSave();
    }
  });

  return {
    saveOnBlur,
  };
}
