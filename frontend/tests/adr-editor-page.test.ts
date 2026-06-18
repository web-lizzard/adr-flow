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
const publishMock = vi.fn().mockResolvedValue(undefined);
const refreshReviewStatusMock = vi.fn().mockResolvedValue(undefined);
const updateTitleMock = vi.fn();
const updateContentMock = vi.fn();
const notifyPublishedMock = vi.hoisted(() => vi.fn());

vi.mock("@/composables/useAdrPublishFeedback", () => ({
  useAdrPublishFeedback: () => ({
    notifyPublished: notifyPublishedMock,
  }),
}));

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
  publish: publishMock,
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
          template: `<button :disabled="disabled" @click="$emit('click')"><slot /></button>`,
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

function findButtonByText(
  wrapper: ReturnType<typeof mountEditorPage>,
  label: string,
) {
  return wrapper.findAll("button").find((button) => button.text() === label);
}

describe("ADR editor page", () => {
  beforeEach(() => {
    saveOnBlurMock.mockClear();
    loadMock.mockClear();
    saveMock.mockClear();
    submitForReviewMock.mockReset();
    submitForReviewMock.mockResolvedValue(undefined);
    publishMock.mockReset();
    publishMock.mockResolvedValue(undefined);
    refreshReviewStatusMock.mockReset();
    updateTitleMock.mockClear();
    updateContentMock.mockClear();
    notifyPublishedMock.mockClear();
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
    expect(findButtonByText(wrapper, "Publish for review")).toBeUndefined();

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
    expect(findButtonByText(wrapper, "Publish for review")?.text()).toBe(
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

    const submitButton = findButtonByText(wrapper, "Publish for review");
    expect(submitButton).toBeDefined();
    await submitButton!.trigger("click");
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

    expect(findButtonByText(wrapper, "Publish for review")).toBeUndefined();
    expect(findButtonByText(wrapper, "Publish")?.text()).toBe("Publish");
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

  it("shows Publish button only in after_review status", async () => {
    currentAdr.value = baseAdr({ status: "draft" });
    const draftWrapper = mountEditorPage();
    await flushPromises();
    expect(findButtonByText(draftWrapper, "Publish")).toBeUndefined();
    expect(findButtonByText(draftWrapper, "Publish for review")).toBeDefined();

    currentAdr.value = baseAdr({ status: "proposed" });
    const proposedWrapper = mountEditorPage();
    await flushPromises();
    expect(findButtonByText(proposedWrapper, "Publish")).toBeUndefined();
    expect(
      findButtonByText(proposedWrapper, "Publish for review"),
    ).toBeUndefined();
  });

  it("saves dirty changes before publishing", async () => {
    currentAdr.value = baseAdr({ status: "after_review" });
    isDirty.value = true;

    const wrapper = mountEditorPage();
    await flushPromises();

    const publishButton = findButtonByText(wrapper, "Publish");
    expect(publishButton).toBeDefined();
    await publishButton!.trigger("click");
    await flushPromises();

    expect(saveMock).toHaveBeenCalledTimes(1);
    expect(publishMock).toHaveBeenCalledWith("adr-1");
  });

  it("disables the editor while publish is in flight", async () => {
    currentAdr.value = baseAdr({ status: "after_review" });
    let resolvePublish: () => void = () => {};
    publishMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolvePublish = resolve;
        }),
    );

    const wrapper = mountEditorPage();
    await flushPromises();

    const publishButton = findButtonByText(wrapper, "Publish");
    await publishButton!.trigger("click");
    await flushPromises();

    const titleInput = wrapper.get('[data-testid="title-input"]');
    const editor = wrapper.get('[data-testid="markdown-editor"]');
    expect((titleInput.element as HTMLInputElement).disabled).toBe(true);
    expect((editor.element as HTMLTextAreaElement).readOnly).toBe(true);

    resolvePublish();
    await flushPromises();
  });

  it("shows proposed status and toast after successful publish", async () => {
    currentAdr.value = baseAdr({ status: "after_review" });

    const wrapper = mountEditorPage();
    await flushPromises();

    const publishButton = findButtonByText(wrapper, "Publish");
    await publishButton!.trigger("click");
    await flushPromises();

    expect(publishMock).toHaveBeenCalledWith("adr-1");
    expect(notifyPublishedMock).toHaveBeenCalledTimes(1);

    currentAdr.value = baseAdr({ status: "proposed" });
    await flushPromises();

    expect(wrapper.findComponent(AdrStatusBadge).text()).toContain("Proposed");
    const titleInput = wrapper.get('[data-testid="title-input"]');
    expect((titleInput.element as HTMLInputElement).disabled).toBe(false);
  });

  it("links back to the workspace", async () => {
    currentAdr.value = baseAdr({ title: "My ADR" });

    const wrapper = mountEditorPage();
    await flushPromises();

    const backLink = wrapper.get('a[href="/workspace"]');
    expect(backLink.text()).toContain("Back to workspace");
  });
});
