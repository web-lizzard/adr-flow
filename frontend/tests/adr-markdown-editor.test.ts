import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import AdrMarkdownEditor from "../app/components/adr/AdrMarkdownEditor.client.vue";

const CodeMirrorStub = {
  name: "CodeMirror",
  props: ["modelValue", "readonly", "extensions"],
  emits: ["update:modelValue", "focus"],
  template: `<div data-testid="codemirror-stub" />`,
};

describe("AdrMarkdownEditor", () => {
  it("passes readonly to CodeMirror and suppresses blur when read-only", async () => {
    const wrapper = mount(AdrMarkdownEditor, {
      props: {
        modelValue: "## Context",
        readonly: true,
      },
      global: {
        stubs: {
          CodeMirror: CodeMirrorStub,
        },
      },
    });

    const editor = wrapper.findComponent(CodeMirrorStub);
    expect(editor.props("readonly")).toBe(true);

    await editor.vm.$emit("focus", false);

    expect(wrapper.emitted("blur")).toBeUndefined();
  });

  it("emits blur when editable and editor loses focus", async () => {
    const wrapper = mount(AdrMarkdownEditor, {
      props: {
        modelValue: "## Context",
      },
      global: {
        stubs: {
          CodeMirror: CodeMirrorStub,
        },
      },
    });

    const editor = wrapper.findComponent(CodeMirrorStub);
    await editor.vm.$emit("focus", false);

    expect(wrapper.emitted("blur")).toHaveLength(1);
  });

  it("does not emit model updates when read-only", async () => {
    const wrapper = mount(AdrMarkdownEditor, {
      props: {
        modelValue: "## Context",
        readonly: true,
      },
      global: {
        stubs: {
          CodeMirror: CodeMirrorStub,
        },
      },
    });

    const editor = wrapper.findComponent(CodeMirrorStub);
    await editor.vm.$emit("update:modelValue", "changed content");

    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });
});
