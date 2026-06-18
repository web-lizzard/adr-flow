<script setup lang="ts">
import { Toaster } from "@/components/ui/sonner";

const auth = useAuth();
</script>

<template>
  <div class="flex min-h-svh flex-col bg-background">
    <Toaster />
    <header class="border-b border-border bg-card px-4 py-3 shadow-sm sm:px-6">
      <div class="mx-auto flex max-w-5xl items-center justify-between">
        <NuxtLink to="/" class="text-lg font-semibold tracking-tight">
          ADR Flow
        </NuxtLink>
        <div class="flex items-center gap-3">
          <span v-if="auth.user" class="text-sm text-muted-foreground">
            {{ auth.user.email }}
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
    <main class="mx-auto w-full max-w-5xl flex-1 p-4 sm:p-6">
      <slot />
    </main>
  </div>
</template>
