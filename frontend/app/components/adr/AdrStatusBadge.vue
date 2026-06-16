<script setup lang="ts">
import { cn } from "@/lib/utils";

const props = defineProps<{
  status: string;
}>();

const statusConfig: Record<string, { label: string; class: string }> = {
  draft: {
    label: "Draft",
    class: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
  },
  in_review: {
    label: "In review",
    class: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  },
  after_review: {
    label: "After review",
    class: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  },
  proposed: {
    label: "Proposed",
    class: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  },
};

const config = computed(
  () =>
    statusConfig[props.status] ?? {
      label: props.status,
      class: "bg-gray-100 text-gray-800",
    },
);
</script>

<template>
  <span
    :class="
      cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        config.class,
      )
    "
  >
    {{ config.label }}
  </span>
</template>
