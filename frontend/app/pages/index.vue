<script setup lang="ts">
definePageMeta({
  layout: "default",
});

const {
  data: health,
  error,
  status,
} = await useAsyncData("health", () =>
  $fetch<{ status: string }>("/api/health"),
);
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-3xl font-bold tracking-tight">ADR Flow</h1>
      <p class="text-muted-foreground">
        Architecture Decision Records with AI-assisted review.
      </p>
    </div>

    <Card>
      <CardHeader>
        <CardTitle>API health</CardTitle>
        <CardDescription>Backend connectivity via Nitro proxy.</CardDescription>
      </CardHeader>
      <CardContent aria-live="polite">
        <p v-if="status === 'pending'" class="text-muted-foreground">
          Checking backend…
        </p>
        <p v-else-if="error" class="text-destructive">
          Unreachable: {{ error.message }}
        </p>
        <p v-else class="font-medium text-primary">
          status: {{ health?.status }}
        </p>
      </CardContent>
      <CardFooter>
        <Button variant="outline" as-child>
          <NuxtLink to="/auth">Preview auth layout</NuxtLink>
        </Button>
      </CardFooter>
    </Card>
  </div>
</template>
