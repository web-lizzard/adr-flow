<script setup lang="ts">
definePageMeta({
  layout: "default",
  middleware: ["auth"],
});

const auth = useAuth();
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
        <CardTitle>Your ADRs</CardTitle>
        <CardDescription>
          Architecture Decision Records will appear here in a future release.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p class="text-sm text-muted-foreground">
          This is your protected landing page. Start documenting decisions once
          the ADR list ships in S-02.
        </p>
      </CardContent>
    </Card>
  </div>
</template>
