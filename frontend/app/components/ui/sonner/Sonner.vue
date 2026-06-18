<script lang="ts" setup>
import type { ToasterProps } from "vue-sonner";
import { reactiveOmit } from "@vueuse/core";
import {
  CircleCheckIcon,
  InfoIcon,
  Loader2Icon,
  OctagonXIcon,
  TriangleAlertIcon,
  XIcon,
} from "lucide-vue-next";
import { Toaster as Sonner } from "vue-sonner";

const props = defineProps<ToasterProps>();
const delegatedProps = reactiveOmit(props, "toastOptions");
</script>

<template>
  <Sonner
    class="toaster group"
    position="top-center"
    :offset="{ top: '35vh' }"
    :toast-options="{
      classes: {
        toast:
          'group toast group-[.toaster]:bg-popover group-[.toaster]:text-popover-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg group-[.toaster]:rounded-lg',
        description: 'group-[.toast]:text-muted-foreground',
        actionButton:
          'group-[.toast]:bg-primary group-[.toast]:text-primary-foreground',
        cancelButton:
          'group-[.toast]:bg-muted group-[.toast]:text-muted-foreground',
      },
    }"
    v-bind="delegatedProps"
  >
    <template #success-icon>
      <CircleCheckIcon
        class="size-4 shrink-0 text-green-600 dark:text-green-400"
      />
    </template>
    <template #info-icon>
      <InfoIcon class="size-4 shrink-0" />
    </template>
    <template #warning-icon>
      <TriangleAlertIcon class="size-4 shrink-0" />
    </template>
    <template #error-icon>
      <OctagonXIcon class="size-4 shrink-0" />
    </template>
    <template #loading-icon>
      <Loader2Icon class="size-4 shrink-0 animate-spin" />
    </template>
    <template #close-icon>
      <XIcon class="size-4 shrink-0" />
    </template>
  </Sonner>
</template>
