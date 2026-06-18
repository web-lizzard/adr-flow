import { toast } from "vue-sonner";

export function useAdrPublishFeedback() {
  function notifyPublished() {
    toast.success("ADR published as proposed");
  }

  return { notifyPublished };
}
