<script setup lang="ts">
const {
  data: health,
  error,
  status,
} = await useAsyncData("health", () =>
  $fetch<{ status: string }>("/api/health"),
);
</script>

<template>
  <div class="page">
    <h1>ADR Flow</h1>
    <section class="health" aria-live="polite">
      <h2>API health</h2>
      <p v-if="status === 'pending'">Checking backend…</p>
      <p v-else-if="error" class="health--error">
        Unreachable: {{ error.message }}
      </p>
      <p v-else class="health--ok">status: {{ health?.status }}</p>
    </section>
  </div>
</template>

<style scoped>
.page {
  font-family:
    system-ui,
    -apple-system,
    sans-serif;
  margin: 2rem auto;
  max-width: 40rem;
  padding: 0 1rem;
}

.health {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  margin-top: 1.5rem;
  padding: 1rem 1.25rem;
}

.health h2 {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
}

.health--ok {
  color: #15803d;
}

.health--error {
  color: #b91c1c;
}
</style>
