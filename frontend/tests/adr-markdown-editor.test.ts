import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("md-editor-v3/lib/style.css", () => ({}));
vi.mock("md-editor-v3/lib/preview.css", () => ({}));

vi.mock("md-editor-v3", async () => {
  const { defineComponent } = await import("vue");

  return {
    MdEditor: defineComponent({
      name: "MdEditor",
      props: ["modelValue", "toolbars", "theme"],
      emits: ["update:modelValue", "on-blur"],
      template: `<div data-testid="md-editor-stub" />`,
    }),
    MdPreview: defineComponent({
      name: "MdPreview",
      props: ["modelValue", "theme"],
      template: `<div data-testid="md-preview-stub" />`,
    }),
  };
});

import AdrMarkdownEditor from "../app/components/adr/AdrMarkdownEditor.client.vue";

function mountEditor(props: { modelValue: string; readonly?: boolean }) {
  return mount(AdrMarkdownEditor, {
    props,
  });
}

describe("AdrMarkdownEditor", () => {
  beforeEach(() => {
    vi.stubGlobal("useColorMode", () => ({
      value: "light",
      preference: "light",
    }));
  });

  it("renders MdPreview and suppresses blur when read-only", () => {
    const wrapper = mountEditor({
      modelValue: "## Context",
      readonly: true,
    });

    expect(wrapper.find('[data-testid="md-preview-stub"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="md-editor-stub"]').exists()).toBe(false);
    expect(wrapper.emitted("blur")).toBeUndefined();
  });

  it("emits blur when editable and editor loses focus", async () => {
    const wrapper = mountEditor({
      modelValue: "## Context",
    });

    await wrapper.findComponent({ name: "MdEditor" }).vm.$emit("on-blur");

    expect(wrapper.emitted("blur")).toHaveLength(1);
  });

  it("does not emit model updates when read-only", async () => {
    const wrapper = mountEditor({
      modelValue: "## Context",
      readonly: true,
    });

    expect(wrapper.find('[data-testid="md-editor-stub"]').exists()).toBe(false);

    await wrapper
      .findComponent({ name: "MdPreview" })
      .vm.$emit("update:modelValue", "changed content");

    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });

  it("renders MdEditor when editable and MdPreview when readonly", () => {
    const editable = mountEditor({ modelValue: "## Context" });
    expect(editable.find('[data-testid="md-editor-stub"]').exists()).toBe(true);
    expect(editable.find('[data-testid="md-preview-stub"]').exists()).toBe(
      false,
    );

    const readonly = mountEditor({
      modelValue: "## Context",
      readonly: true,
    });
    expect(readonly.find('[data-testid="md-preview-stub"]').exists()).toBe(
      true,
    );
    expect(readonly.find('[data-testid="md-editor-stub"]').exists()).toBe(
      false,
    );
  });
});
