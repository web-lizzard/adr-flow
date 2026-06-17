<script setup lang="ts">
import AdrReviewAnnotations from "@/components/adr/AdrReviewAnnotations.vue";
import AdrStatusBadge from "@/components/adr/AdrStatusBadge.vue";
import Button from "@/components/ui/button/Button.vue";
import { getAuthErrorMessage } from "@/stores/auth";

definePageMeta({
  layout: "default",
  middleware: ["auth"],
});

const route = useRoute();
const adr = useAdr();
const adrStore = useAdrStore();

const adrId = computed(() => String(route.params.id));
const titleError = ref<string | null>(null);
const submitError = ref<string | null>(null);
const loadError = ref<string | null>(null);
const isSubmitting = ref(false);
const isReadOnly = computed(
  () => adr.currentAdr.value?.status === "in_review" || isSubmitting.value,
);
const showSubmitButton = computed(
  () => adr.currentAdr.value?.status === "draft",
);
const showReviewPanel = computed(() => {
  const current = adr.currentAdr.value;
  if (!current) {
    return false;
  }
  return (
    (current.reviewAnnotations?.length ?? 0) > 0 ||
    current.reviewError !== null ||
    current.status === "after_review"
  );
});

const { saveOnBlur } = useAdrPersistence(adrId, adrStore, isSubmitting);
const { isPolling, pollError } = useAdrReviewPolling(adrId, adr);

async function loadCurrentAdr(id: string) {
  loadError.value = null;
  try {
    await adr.load(id);
  } catch (error) {
    loadError.value = getAuthErrorMessage(error, "Failed to load ADR");
  }
}

onMounted(() => {
  void loadCurrentAdr(adrId.value);
});

watch(adrId, (id) => {
  void loadCurrentAdr(id);
});

async function onTitleBlur() {
  if (isReadOnly.value) {
    return;
  }
  try {
    titleError.value = null;
    await saveOnBlur();
  } catch (error) {
    titleError.value = getAuthErrorMessage(error, "Failed to save title");
  }
}

async function onEditorBlur() {
  if (isReadOnly.value) {
    return;
  }
  try {
    titleError.value = null;
    await saveOnBlur();
  } catch (error) {
    titleError.value = getAuthErrorMessage(error, "Failed to save content");
  }
}

function onTitleInput(value: string | number) {
  if (isReadOnly.value) {
    return;
  }
  titleError.value = null;
  adr.updateTitle(String(value));
}

function onContentInput(value: string) {
  if (isReadOnly.value) {
    return;
  }
  titleError.value = null;
  adr.updateContent(value);
}

async function onSubmitForReview() {
  if (!showSubmitButton.value || isSubmitting.value) {
    return;
  }

  submitError.value = null;
  isSubmitting.value = true;
  try {
    if (adr.isDirty.value) {
      await adr.save();
    }
    await adr.submitForReview(adrId.value);
  } catch (error) {
    submitError.value = getAuthErrorMessage(
      error,
      "Failed to submit for review",
    );
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <div class="space-y-6">
    <NuxtLink
      to="/workspace"
      class="inline-flex items-center text-sm text-muted-foreground transition-colors hover:text-foreground"
    >
      ← Back to workspace
    </NuxtLink>

    <div class="flex flex-wrap items-center gap-3">
      <h1 class="text-3xl font-bold tracking-tight">Edit ADR</h1>
      <AdrStatusBadge
        v-if="adr.currentAdr.value"
        :status="adr.currentAdr.value.status"
      />
    </div>

    <p v-if="isReadOnly" class="text-muted-foreground">
      This ADR is being reviewed and cannot be edited.
      <span v-if="isPolling"> Checking for review results…</span>
    </p>
    <p v-if="pollError" class="text-sm text-destructive">
      {{ pollError }}
    </p>
    <p v-else class="text-muted-foreground">
      Draft changes save when you click away or leave this tab.
    </p>

    <div v-if="showSubmitButton" class="flex flex-wrap items-center gap-3">
      <Button
        type="button"
        :disabled="adr.loading.value || isSubmitting"
        @click="onSubmitForReview"
      >
        Publish for review
      </Button>
      <p v-if="submitError" class="text-sm text-destructive">
        {{ submitError }}
      </p>
    </div>

    <div
      v-if="loadError"
      class="space-y-3 rounded-lg border border-destructive/40 bg-destructive/10 p-4"
    >
      <p class="text-sm text-destructive">{{ loadError }}</p>
      <NuxtLink
        to="/workspace"
        class="inline-flex text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        ← Back to workspace
      </NuxtLink>
    </div>

    <div
      v-else-if="adr.loading.value && !adr.currentAdr.value"
      class="space-y-4"
    >
      <div class="h-9 w-full animate-pulse rounded-md bg-muted" />
      <div class="h-96 w-full animate-pulse rounded-md bg-muted" />
    </div>

    <div v-else-if="adr.currentAdr.value" class="space-y-4">
      <div class="space-y-2">
        <Label for="adr-title">Title</Label>
        <Input
          id="adr-title"
          :model-value="adr.currentAdr.value.title"
          :disabled="isReadOnly"
          @update:model-value="onTitleInput"
          @blur="onTitleBlur"
        />
        <p v-if="titleError" class="text-sm text-destructive">
          {{ titleError }}
        </p>
      </div>

      <ClientOnly>
        <AdrMarkdownEditor
          :model-value="adr.currentAdr.value.content"
          :readonly="isReadOnly"
          @update:model-value="onContentInput"
          @blur="onEditorBlur"
        />
        <template #fallback>
          <div class="h-96 w-full animate-pulse rounded-md bg-muted" />
        </template>
      </ClientOnly>

      <AdrReviewAnnotations
        v-if="showReviewPanel"
        :annotations="adr.currentAdr.value.reviewAnnotations"
        :review-error="adr.currentAdr.value.reviewError"
        :status="adr.currentAdr.value.status"
      />
    </div>
  </div>
</template>
