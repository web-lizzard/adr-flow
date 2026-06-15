<script setup lang="ts">
import { Moon, Sun } from "@lucide/vue";

const colorMode = useColorMode();

function toggleTheme() {
  colorMode.preference = colorMode.value === "dark" ? "light" : "dark";
}
</script>

<template>
  <Button
    variant="ghost"
    size="icon"
    class="relative"
    aria-label="Toggle theme"
    @click="toggleTheme"
  >
    <Sun
      class="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0"
    />
    <Moon
      class="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100"
    />
  </Button>
</template>
