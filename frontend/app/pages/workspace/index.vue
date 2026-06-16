<script setup lang="ts">
import { useDebounceFn } from "@vueuse/core";

definePageMeta({
  layout: "default",
  middleware: ["auth"],
});

const auth = useAuth();
const adr = useAdr();

const title = ref("");
const titleError = ref<string | null>(null);
const checkingTitle = ref(false);
const formError = ref<string | null>(null);

const canSubmit = computed(
  () =>
    title.value.trim().length > 0 &&
    !titleError.value &&
    !checkingTitle.value &&
    !adr.loading.value,
);

onMounted(() => {
  void adr.fetchList();
});

const checkTitleUniqueness = useDebounceFn(async (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    titleError.value = null;
    checkingTitle.value = false;
    return;
  }

  checkingTitle.value = true;
  try {
    const results = await adr.searchByTitle(trimmed);
    const duplicate = results.some(
      (result) => result.title.toLowerCase() === trimmed.toLowerCase(),
    );
    titleError.value = duplicate
      ? "An ADR with this title already exists"
      : null;
  } catch {
    titleError.value = null;
  } finally {
    checkingTitle.value = false;
  }
}, 300);

watch(title, (value) => {
  formError.value = null;
  checkingTitle.value = true;
  void checkTitleUniqueness(value);
});

async function onSubmit() {
  if (!canSubmit.value) {
    return;
  }

  formError.value = null;
  try {
    await adr.create(title.value.trim());
  } catch (error) {
    if (
      typeof error === "object" &&
      error !== null &&
      "statusCode" in error &&
      (error as { statusCode?: number }).statusCode === 409
    ) {
      titleError.value = "An ADR with this title already exists";
      return;
    }

    formError.value = getAuthErrorMessage(error, "Failed to create ADR");
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold tracking-tight">Workspace</h1>
      <p class="text-muted-foreground">
        Welcome back{{ auth.user.value ? `, ${auth.user.value.email}` : "" }}.
      </p>
    </div>

    <Card>
      <CardHeader>
        <CardTitle>Create ADR</CardTitle>
        <CardDescription>
          Start a new architecture decision record from the starter template.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form class="space-y-4" @submit.prevent="onSubmit">
          <div class="space-y-2">
            <Label for="adr-create-title">Title</Label>
            <Input
              id="adr-create-title"
              v-model="title"
              placeholder="e.g. Use PostgreSQL for persistence"
              required
              minlength="1"
            />
            <p v-if="titleError" class="text-sm text-destructive">
              {{ titleError }}
            </p>
            <p v-else-if="checkingTitle" class="text-sm text-muted-foreground">
              Checking title availability...
            </p>
          </div>

          <p v-if="formError" class="text-sm text-destructive">
            {{ formError }}
          </p>

          <Button type="submit" :disabled="!canSubmit">
            {{ adr.loading.value ? "Creating..." : "Create ADR" }}
          </Button>
        </form>
      </CardContent>
    </Card>

    <section class="space-y-3" aria-label="Your ADRs">
      <h2 class="text-xl font-semibold tracking-tight">Your ADRs</h2>

      <p v-if="adr.listLoading.value" class="text-sm text-muted-foreground">
        Loading ADR history...
      </p>
      <p v-else-if="adr.listError.value" class="text-sm text-destructive">
        {{ adr.listError.value }}
      </p>
    </section>
  </div>
</template>
