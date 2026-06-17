import { flushPromises, mount } from "@vue/test-utils";
import { computed, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdrReviewAnnotations from "../app/components/adr/AdrReviewAnnotations.vue";
import AdrStatusBadge from "../app/components/adr/AdrStatusBadge.vue";
import EditorPage from "../app/pages/workspace/adr/[id].vue";

const saveOnBlurMock = vi.fn().mockResolvedValue(undefined);
const loadMock = vi.fn().mockResolvedValue(undefined);
const saveMock = vi.fn().mockResolvedValue(undefined);
const submitForReviewMock = vi.fn().mockResolvedValue(undefined);
const refreshReviewStatusMock = vi.fn().mockResolvedValue(undefined);
const updateTitleMock = vi.fn();
const updateContentMock = vi.fn();

const currentAdr = ref<{
  id: string;
  title: string;
  content: string;
  status: string;
  createdAt: string;
  updatedAt: string;
  reviewAnnotations: Array<{
    kind: string;
    message: string;
    location?: string | null;
    suggestion?: string | null;
  }> | null;
  reviewedAt: string | null;
  reviewError: {
    source_event_id: string;
    code: string;
    message: string;
    failed_at: string;
  } | null;
} | null>(null);
const loading = ref(false);
const isDirty = ref(false);

vi.stubGlobal("definePageMeta", vi.fn());
vi.stubGlobal("useRoute", () => ({
  params: { id: "adr-1" },
}));
vi.stubGlobal("useAdrStore", () => ({}));
vi.stubGlobal("useAdr", () => ({
  currentAdr: computed(() => currentAdr.value),
  loading: computed(() => loading.value),
  isDirty: computed(() => isDirty.value),
  load: loadMock,
  save: saveMock,
  submitForReview: submitForReviewMock,
  refreshReviewStatus: refreshReviewStatusMock,
  updateTitle: updateTitleMock,
  updateContent: updateContentMock,
}));
vi.stubGlobal("useAdrPersistence", () => ({
  saveOnBlur: saveOnBlurMock,
}));
vi.stubGlobal("useAdrReviewPolling", () => ({
  isPolling: computed(
    () =>
      currentAdr.value?.status === "in_review" &&
      currentAdr.value.reviewError === null,
  ),
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
        Button: {
          props: ["disabled"],
          emits: ["click"],
          template: `<button
            data-testid="submit-review-button"
            :disabled="disabled"
            @click="$emit('click')"
          ><slot /></button>`,
        },
      },
    },
  });
}

function baseAdr(
  overrides: Partial<NonNullable<typeof currentAdr.value>> = {},
) {
  return {
    id: "adr-1",
    title: "Editable ADR",
    content: "## Context",
    status: "draft",
    createdAt: "2026-06-16T10:00:00Z",
    updatedAt: "2026-06-16T10:00:00Z",
    reviewAnnotations: null,
    reviewedAt: null,
    reviewError: null,
    ...overrides,
  };
}

describe("ADR editor page", () => {
  beforeEach(() => {
    saveOnBlurMock.mockClear();
    loadMock.mockClear();
    saveMock.mockClear();
    submitForReviewMock.mockClear();
    refreshReviewStatusMock.mockClear();
    updateTitleMock.mockClear();
    updateContentMock.mockClear();
    loading.value = false;
    isDirty.value = false;
    currentAdr.value = null;
  });

  it("shows read-only UX for in_review ADRs", async () => {
    currentAdr.value = baseAdr({ status: "in_review", title: "Locked ADR" });

    const wrapper = mountEditorPage();
    await flushPromises();

    expect(wrapper.text()).toContain(
      "This ADR is being reviewed and cannot be edited.",
    );
    expect(wrapper.text()).toContain("Checking for review results");
    expect(wrapper.findComponent(AdrStatusBadge).text()).toContain("In review");
    expect(wrapper.find('[data-testid="submit-review-button"]').exists()).toBe(
      false,
    );

    const titleInput = wrapper.get('[data-testid="title-input"]');
    expect((titleInput.element as HTMLInputElement).disabled).toBe(true);

    const editor = wrapper.get('[data-testid="markdown-editor"]');
    expect((editor.element as HTMLTextAreaElement).readOnly).toBe(true);

    await editor.trigger("blur");
    expect(saveOnBlurMock).not.toHaveBeenCalled();
  });

  it("remains editable for draft ADRs and saves on blur", async () => {
    currentAdr.value = baseAdr();

    const wrapper = mountEditorPage();
    await flushPromises();

    expect(wrapper.text()).not.toContain(
      "This ADR is being reviewed and cannot be edited.",
    );
    expect(wrapper.findComponent(AdrStatusBadge).text()).toContain("Draft");
    expect(wrapper.get('[data-testid="submit-review-button"]').text()).toBe(
      "Publish for review",
    );

    const titleInput = wrapper.get('[data-testid="title-input"]');
    expect((titleInput.element as HTMLInputElement).disabled).toBe(false);

    await titleInput.trigger("blur");
    expect(saveOnBlurMock).toHaveBeenCalledTimes(1);
  });

  it("saves dirty changes before submitting for review", async () => {
    currentAdr.value = baseAdr();
    isDirty.value = true;

    const wrapper = mountEditorPage();
    await flushPromises();

    await wrapper.get('[data-testid="submit-review-button"]').trigger("click");
    await flushPromises();

    expect(saveMock).toHaveBeenCalledTimes(1);
    expect(submitForReviewMock).toHaveBeenCalledWith("adr-1");
  });

  it("remains editable for after_review ADRs and hides submit CTA", async () => {
    currentAdr.value = baseAdr({
      status: "after_review",
      reviewAnnotations: [
        {
          kind: "missing_section",
          message: "Add a Consequences section",
        },
      ],
      reviewedAt: "2026-06-16T12:00:00Z",
    });

    const wrapper = mountEditorPage();
    await flushPromises();

    expect(wrapper.find('[data-testid="submit-review-button"]').exists()).toBe(
      false,
    );
    expect(wrapper.findComponent(AdrStatusBadge).text()).toContain(
      "After review",
    );

    const titleInput = wrapper.get('[data-testid="title-input"]');
    expect((titleInput.element as HTMLInputElement).disabled).toBe(false);

    await titleInput.trigger("blur");
    expect(saveOnBlurMock).toHaveBeenCalledTimes(1);
    expect(wrapper.findComponent(AdrReviewAnnotations).exists()).toBe(true);
  });

  it("shows review error metadata in the annotation panel", async () => {
    currentAdr.value = baseAdr({
      status: "in_review",
      reviewError: {
        source_event_id: "evt-1",
        code: "validation_failed",
        message: "Review output was invalid",
        failed_at: "2026-06-16T12:00:00Z",
      },
    });

    const wrapper = mountEditorPage();
    await flushPromises();

    expect(wrapper.findComponent(AdrReviewAnnotations).exists()).toBe(true);
    expect(wrapper.text()).toContain("Review output was invalid");
    expect(wrapper.text()).not.toContain("Checking for review results");
  });

  it("shows annotations after review completes via polling", async () => {
    currentAdr.value = baseAdr({ status: "in_review" });

    const wrapper = mountEditorPage();
    await flushPromises();

    expect(wrapper.text()).toContain("Checking for review results");

    currentAdr.value = baseAdr({
      status: "after_review",
      reviewAnnotations: [
        {
          kind: "missing_section",
          message: "Add a Decision section",
          location: "## Decision",
          suggestion: "Document the chosen option.",
        },
      ],
      reviewedAt: "2026-06-16T12:00:00Z",
    });
    await flushPromises();

    expect(wrapper.findComponent(AdrReviewAnnotations).exists()).toBe(true);
    expect(wrapper.text()).toContain("Add a Decision section");
    expect(wrapper.text()).not.toContain("Checking for review results");
  });

  it("links back to the workspace", async () => {
    currentAdr.value = baseAdr({ title: "My ADR" });

    const wrapper = mountEditorPage();
    await flushPromises();

    const backLink = wrapper.get('a[href="/workspace"]');
    expect(backLink.text()).toContain("Back to workspace");
  });
});
