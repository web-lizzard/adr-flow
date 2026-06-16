import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import AdrCard from "../app/components/adr/AdrCard.vue";

const navigateToMock = vi.fn();
vi.stubGlobal("navigateTo", navigateToMock);

describe("AdrCard", () => {
  it("renders title, status badge label, and formatted last-edited date", () => {
    const wrapper = mount(AdrCard, {
      props: {
        id: "adr-1",
        title: "Use PostgreSQL for persistence",
        status: "draft",
        updatedAt: "2026-06-16T10:00:00Z",
      },
    });

    expect(wrapper.text()).toContain("Use PostgreSQL for persistence");
    expect(wrapper.text()).toContain("Draft");
    expect(wrapper.text()).toContain("Jun 16, 2026, 10:00 AM");
  });

  it("navigates to the ADR editor when clicked", async () => {
    const wrapper = mount(AdrCard, {
      props: {
        id: "adr-42",
        title: "Cache strategy",
        status: "proposed",
        updatedAt: "2026-06-16T12:00:00Z",
      },
    });

    await wrapper.trigger("click");

    expect(navigateToMock).toHaveBeenCalledWith("/workspace/adr/adr-42");
  });
});
