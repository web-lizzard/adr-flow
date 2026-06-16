import { flushPromises, mount } from "@vue/test-utils";
import { computed, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdrStatusBadge from "../app/components/adr/AdrStatusBadge.vue";
import EditorPage from "../app/pages/workspace/adr/[id].vue";

const saveOnBlurMock = vi.fn().mockResolvedValue(undefined);
const loadMock = vi.fn().mockResolvedValue(undefined);
const updateTitleMock = vi.fn();
const updateContentMock = vi.fn();

const currentAdr = ref<{
  id: string;
  title: string;
  content: string;
  status: string;
  createdAt: string;
  updatedAt: string;
} | null>(null);
const loading = ref(false);

vi.stubGlobal("definePageMeta", vi.fn());
vi.stubGlobal("useRoute", () => ({
  params: { id: "adr-1" },
}));
vi.stubGlobal("useAdrStore", () => ({}));
vi.stubGlobal("useAdr", () => ({
  currentAdr: computed(() => currentAdr.value),
  loading: computed(() => loading.value),
  load: loadMock,
  updateTitle: updateTitleMock,
  updateContent: updateContentMock,
}));
vi.stubGlobal("useAdrPersistence", () => ({
  saveOnBlur: saveOnBlurMock,
}));

function mountEditorPage() {
  return mount(EditorPage, {
    global: {
      stubs: {
        ClientOnly: { template: "<slot />" },
        NuxtLink: {
          props: ["to"],
          template: `<a :href="to"><slot /></a>`,
        },
        AdrMarkdownEditor: {
          props: ["modelValue", "readonly"],
          emits: ["update:modelValue", "blur"],
          template: `<textarea
            data-testid="markdown-editor"
            :readonly="readonly"
            :value="modelValue"
            @blur="$emit('blur')"
          />`,
        },
        Label: { template: "<label><slot /></label>" },
        Input: {
          props: ["modelValue", "disabled"],
          emits: ["update:modelValue", "blur"],
          template: `<input
            data-testid="title-input"
            :value="modelValue"
            :disabled="disabled"
            @input="$emit('update:modelValue', $event.target.value)"
            @blur="$emit('blur')"
          />`,
        },
      },
    },
  });
}

describe("ADR editor page", () => {
  beforeEach(() => {
    saveOnBlurMock.mockClear();
    loadMock.mockClear();
    updateTitleMock.mockClear();
    updateContentMock.mockClear();
    loading.value = false;
    currentAdr.value = null;
  });

  it("shows read-only UX for in_review ADRs", async () => {
    currentAdr.value = {
      id: "adr-1",
      title: "Locked ADR",
      content: "## Context",
      status: "in_review",
      createdAt: "2026-06-16T10:00:00Z",
      updatedAt: "2026-06-16T10:00:00Z",
    };

    const wrapper = mountEditorPage();
    await flushPromises();

    expect(wrapper.text()).toContain(
      "This ADR is being reviewed and cannot be edited.",
    );
    expect(wrapper.findComponent(AdrStatusBadge).text()).toContain("In review");

    const titleInput = wrapper.get('[data-testid="title-input"]');
    expect((titleInput.element as HTMLInputElement).disabled).toBe(true);

    const editor = wrapper.get('[data-testid="markdown-editor"]');
    expect((editor.element as HTMLTextAreaElement).readOnly).toBe(true);

    await editor.trigger("blur");
    expect(saveOnBlurMock).not.toHaveBeenCalled();
  });

  it("remains editable for draft ADRs and saves on blur", async () => {
    currentAdr.value = {
      id: "adr-1",
      title: "Editable ADR",
      content: "## Context",
      status: "draft",
      createdAt: "2026-06-16T10:00:00Z",
      updatedAt: "2026-06-16T10:00:00Z",
    };

    const wrapper = mountEditorPage();
    await flushPromises();

    expect(wrapper.text()).not.toContain(
      "This ADR is being reviewed and cannot be edited.",
    );
    expect(wrapper.findComponent(AdrStatusBadge).text()).toContain("Draft");

    const titleInput = wrapper.get('[data-testid="title-input"]');
    expect((titleInput.element as HTMLInputElement).disabled).toBe(false);

    await titleInput.trigger("blur");
    expect(saveOnBlurMock).toHaveBeenCalledTimes(1);
  });

  it("links back to the workspace", async () => {
    currentAdr.value = {
      id: "adr-1",
      title: "My ADR",
      content: "## Context",
      status: "draft",
      createdAt: "2026-06-16T10:00:00Z",
      updatedAt: "2026-06-16T10:00:00Z",
    };

    const wrapper = mountEditorPage();
    await flushPromises();

    const backLink = wrapper.get('a[href="/workspace"]');
    expect(backLink.text()).toContain("Back to workspace");
  });
});
