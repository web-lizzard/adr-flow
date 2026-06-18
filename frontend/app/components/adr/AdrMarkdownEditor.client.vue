<script setup lang="ts">
import { MdEditor, MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import "md-editor-v3/lib/preview.css";
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

const colorMode = useColorMode();
const editorTheme = computed(() =>
  colorMode.value === "dark" ? "dark" : "light",
);

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
    <MdPreview
      v-if="props.readonly"
      id="adr-editor"
      :model-value="props.modelValue"
      :theme="editorTheme"
      preview-theme="github"
      language="en-US"
      class="h-full w-full"
    />
    <MdEditor
      v-else
      id="adr-editor"
      :model-value="props.modelValue"
      :toolbars="adrToolbars"
      :theme="editorTheme"
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
  --md-color: var(--foreground);
  --md-hover-color: var(--foreground);
  --md-bk-color: var(--background);
  --md-bk-color-outstand: var(--muted);
  --md-bk-hover-color: var(--accent);
  --md-border-color: var(--border);
  --md-border-hover-color: var(--ring);
  --md-border-active-color: var(--ring);
  min-height: 24rem;
  border: none;
  border-radius: var(--radius);
  background-color: var(--background);
  color: var(--foreground);
}

.adr-markdown-editor :deep(.md-editor-toolbar-wrapper) {
  background-color: var(--muted);
  border-block-end-color: var(--border);
}

.adr-markdown-editor :deep(.md-editor-toolbar-item:not([disabled]):hover),
.adr-markdown-editor :deep(.md-editor-toolbar-active) {
  background-color: var(--accent);
  color: var(--accent-foreground);
}

.adr-markdown-editor :deep(.md-editor-content),
.adr-markdown-editor :deep(.md-editor-input-wrapper),
.adr-markdown-editor :deep(.cm-scroller) {
  background-color: var(--background);
}

.adr-markdown-editor :deep(.cm-editor.cm-focused) {
  outline: 2px solid var(--ring);
  outline-offset: -2px;
}

.adr-markdown-editor :deep(.md-editor-preview) {
  --md-theme-color: var(--foreground);
  --md-theme-bg-color: var(--background);
  --md-theme-border-color: var(--border);
  --md-theme-color-hover: var(--accent);
  --md-theme-color-hover-inset: var(--muted);
  --md-theme-bg-color-inset: var(--muted);
  --md-theme-code-bg-color: var(--muted);
  --md-theme-code-block-bg-color: var(--muted);
  --md-theme-blockquote-bg-color: var(--muted);
  --md-theme-blockquote-border-color: var(--border);
  --md-theme-table-border-color: var(--border);
  --md-theme-table-thead-bg-color: var(--muted);
  background-color: var(--background);
  color: var(--foreground);
}

.adr-markdown-editor :deep(.md-editor-previewOnly) {
  min-height: 24rem;
}

.adr-markdown-editor :deep(.cm-scroller) {
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
    "Courier New", monospace;
}
</style>
