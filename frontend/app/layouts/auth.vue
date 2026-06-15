<template>
  <div
    class="relative flex min-h-svh flex-col items-center justify-center bg-muted p-6"
  >
    <div class="absolute right-4 top-4">
      <ThemeToggle />
    </div>
    <div class="w-full max-w-sm">
      <slot />
    </div>
  </div>
</template>
