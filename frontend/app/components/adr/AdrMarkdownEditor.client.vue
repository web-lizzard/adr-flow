<script setup lang="ts">
import { MdEditor } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { computed } from "vue";
import { adrToolbars } from "./adr-editor-toolbars";

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

const toolbars = computed(() => (props.readonly ? [] : adrToolbars));

function onUpdate(value: string) {
  if (props.readonly) {
    return;
  }
  emit("update:modelValue", value);
}

function onBlur() {
  if (!props.readonly) {
    emit("blur");
  }
}
</script>

<template>
  <div
    class="adr-markdown-editor min-h-[24rem] w-full overflow-hidden rounded-md border border-input text-sm"
  >
    <MdEditor
      id="adr-editor"
      :model-value="props.modelValue"
      :read-only="props.readonly"
      :toolbars="toolbars"
      no-upload-img
      language="en-US"
      preview-theme="github"
      code-theme="atom"
      class="h-full w-full"
      @update:model-value="onUpdate"
      @on-blur="onBlur"
    />
  </div>
</template>

<style scoped>
.adr-markdown-editor :deep(.md-editor) {
  min-height: 24rem;
}

.adr-markdown-editor :deep(.cm-scroller) {
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
}
</style>
