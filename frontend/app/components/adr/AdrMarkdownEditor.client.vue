<script setup lang="ts">
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import CodeMirror from "vue-codemirror6";

const props = withDefaults(
  defineProps<{
    modelValue: string;
    readonly?: boolean;
  }>(),
  {
    readonly: false,
  },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "blur"): void;
}>();

const extensions = [markdown({ base: markdownLanguage })];

function onUpdate(value?: string) {
  if (props.readonly || typeof value !== "string") {
    return;
  }
  emit("update:modelValue", value);
}

function onFocus(focused: boolean) {
  if (!focused && !props.readonly) {
    emit("blur");
  }
}
</script>

<template>
  <CodeMirror
    :model-value="props.modelValue"
    :readonly="props.readonly"
    :extensions="extensions"
    basic
    wrap
    class="adr-markdown-editor min-h-[24rem] w-full overflow-hidden rounded-md border border-input text-sm"
    @update:model-value="onUpdate"
    @focus="onFocus"
  />
</template>

<style scoped>
.adr-markdown-editor :deep(.cm-editor) {
  min-height: 24rem;
}

.adr-markdown-editor :deep(.cm-scroller) {
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
}
</style>
