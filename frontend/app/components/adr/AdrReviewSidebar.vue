<script setup lang="ts">
import type {
  ReviewAnnotation,
  ReviewError,
  SectionRating,
} from "@/stores/adr";
import AdrReviewAnnotations from "@/components/adr/AdrReviewAnnotations.vue";
import Button from "@/components/ui/button/Button.vue";

defineProps<{
  open: boolean;
  annotations: ReviewAnnotation[] | null;
  sectionRatings?: SectionRating[] | null;
  reviewError: ReviewError | null;
  status?: string;
  retrying?: boolean;
}>();

const emit = defineEmits<{
  close: [];
  retry: [];
}>();
</script>

<template>
  <aside
    v-if="open"
    class="flex w-full shrink-0 flex-col border-border bg-card lg:sticky lg:top-6 lg:w-80 lg:self-start lg:border-l xl:w-96"
    aria-label="Review feedback"
  >
    <div
      class="flex items-center justify-between gap-2 border-b border-border px-4 py-3"
    >
      <h2 class="text-sm font-semibold">Review feedback</h2>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        class="h-8 px-2 text-muted-foreground"
        aria-label="Close review sidebar"
        @click="emit('close')"
      >
        Close
      </Button>
    </div>
    <div class="max-h-[calc(100svh-8rem)] overflow-y-auto p-4">
      <AdrReviewAnnotations
        :annotations="annotations"
        :section-ratings="sectionRatings"
        :review-error="reviewError"
        :status="status"
        :show-title="false"
        :retrying="retrying"
        @retry="emit('retry')"
      />
    </div>
  </aside>
</template>
