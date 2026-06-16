<script setup lang="ts">
import AdrStatusBadge from "@/components/adr/AdrStatusBadge.vue";

definePageMeta({
  layout: "default",
  middleware: ["auth"],
});

const route = useRoute();
const adr = useAdr();
const adrStore = useAdrStore();

const adrId = computed(() => String(route.params.id));
const titleError = ref<string | null>(null);
const isReadOnly = computed(() => adr.currentAdr.value?.status === "in_review");

const { saveOnBlur } = useAdrPersistence(adrId, adrStore);

onMounted(async () => {
  await adr.load(adrId.value);
});

async function onTitleBlur() {
  if (isReadOnly.value) {
    return;
  }
  try {
    titleError.value = null;
    await saveOnBlur();
  } catch (error) {
    titleError.value = getAdrErrorMessage(error, "Failed to save title");
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
    titleError.value = getAdrErrorMessage(error, "Failed to save content");
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

function getAdrErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null && "data" in error) {
    const detail = (error as { data?: { detail?: unknown } }).data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
  }
  return fallback;
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
    </p>
    <p v-else class="text-muted-foreground">
      Draft changes save when you click away or leave this tab.
    </p>

    <div v-if="adr.loading.value && !adr.currentAdr.value" class="space-y-4">
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
    </div>
  </div>
</template>
