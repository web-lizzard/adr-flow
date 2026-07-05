import { toast } from "vue-sonner";

export function useAdrRemoveFeedback() {
  function notifyRemoved() {
    toast.success("ADR removed from your list");
  }

  return { notifyRemoved };
}
