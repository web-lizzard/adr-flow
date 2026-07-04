<script setup lang="ts">
import type {
  ReviewAnnotation,
  ReviewError,
  SectionRating,
} from "@/stores/adr";

const props = defineProps<{
  annotations: ReviewAnnotation[] | null;
  sectionRatings?: SectionRating[] | null;
  reviewError: ReviewError | null;
  status?: string;
  showTitle?: boolean;
}>();

const kindLabels: Record<string, string> = {
  missing_section: "Missing section",
  inconsistency: "Inconsistency",
  conciseness: "Conciseness",
};

const groupedAnnotations = computed(() => {
  const groups = new Map<string, ReviewAnnotation[]>();
  for (const annotation of props.annotations ?? []) {
    const existing = groups.get(annotation.kind) ?? [];
    existing.push(annotation);
    groups.set(annotation.kind, existing);
  }
  return groups;
});

const hasAnnotations = computed(() => (props.annotations?.length ?? 0) > 0);
const hasRatings = computed(() => (props.sectionRatings?.length ?? 0) > 0);

const showEmptyState = computed(
  () =>
    props.status === "after_review" &&
    !props.reviewError &&
    !hasAnnotations.value &&
    !hasRatings.value,
);
</script>

<template>
  <section
    :class="
      showTitle !== false ? 'space-y-4 rounded-lg border p-4' : 'space-y-4'
    "
  >
    <h2 v-if="showTitle !== false" class="text-lg font-semibold">
      Review feedback
    </h2>

    <div
      v-if="reviewError"
      class="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm"
      role="alert"
    >
      <p class="font-medium text-destructive">Review failed</p>
      <p class="mt-1 text-muted-foreground">{{ reviewError.message }}</p>
    </div>

    <p v-else-if="showEmptyState" class="text-sm text-muted-foreground">
      No review annotations
    </p>

    <div v-else class="space-y-4">
      <div
        v-for="[kind, items] in groupedAnnotations"
        :key="kind"
        class="space-y-2"
      >
        <h3 class="text-sm font-medium">
          {{ kindLabels[kind] ?? kind }}
        </h3>
        <ul class="space-y-2">
          <li
            v-for="(annotation, index) in items"
            :key="`${kind}-${index}`"
            class="rounded-md bg-muted/50 p-3 text-sm"
          >
            <p>{{ annotation.message }}</p>
            <p
              v-if="annotation.location"
              class="mt-1 font-mono text-xs text-muted-foreground"
            >
              {{ annotation.location }}
            </p>
            <p v-if="annotation.suggestion" class="mt-1 text-muted-foreground">
              Suggestion: {{ annotation.suggestion }}
            </p>
          </li>
        </ul>
      </div>

      <div v-if="hasRatings" class="space-y-2">
        <h3 class="text-sm font-medium">Section ratings</h3>
        <ul class="space-y-2">
          <li
            v-for="rating in sectionRatings"
            :key="rating.section"
            class="rounded-md bg-muted/50 p-3 text-sm"
          >
            <p class="font-medium">
              {{ rating.section }}
              <span class="text-muted-foreground">{{ rating.score }}/5</span>
            </p>
            <p v-if="rating.feedback" class="mt-1 text-muted-foreground">
              {{ rating.feedback }}
            </p>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>
