import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdrCard from "../app/components/adr/AdrCard.vue";

const navigateToMock = vi.fn();
vi.stubGlobal("navigateTo", navigateToMock);

const alertDialogStubs = {
  AlertDialog: { template: "<div><slot /></div>" },
  AlertDialogTrigger: { template: "<div><slot /></div>" },
  AlertDialogContent: { template: "<div><slot /></div>" },
  AlertDialogHeader: { template: "<div><slot /></div>" },
  AlertDialogTitle: { template: "<div><slot /></div>" },
  AlertDialogDescription: { template: "<div><slot /></div>" },
  AlertDialogFooter: { template: "<div><slot /></div>" },
  AlertDialogCancel: { template: "<button type='button'>Cancel</button>" },
  AlertDialogAction: { template: "<div><slot /></div>" },
};

function mountAdrCard(props: {
  id: string;
  title: string;
  status: string;
  updatedAt: string;
  removing?: boolean;
}) {
  return mount(AdrCard, {
    props,
    global: {
      stubs: alertDialogStubs,
    },
  });
}

describe("AdrCard", () => {
  beforeEach(() => {
    navigateToMock.mockReset();
  });

  it("renders title, status badge label, and formatted last-edited date", () => {
    const wrapper = mountAdrCard({
      id: "adr-1",
      title: "Use PostgreSQL for persistence",
      status: "draft",
      updatedAt: "2026-06-16T10:00:00Z",
    });

    expect(wrapper.text()).toContain("Use PostgreSQL for persistence");
    expect(wrapper.text()).toContain("Draft");
    expect(wrapper.text()).toContain("Jun 16, 2026, 10:00 AM");
  });

  it("navigates to the ADR editor when clicked", async () => {
    const wrapper = mountAdrCard({
      id: "adr-42",
      title: "Cache strategy",
      status: "proposed",
      updatedAt: "2026-06-16T12:00:00Z",
    });

    await wrapper.trigger("click");

    expect(navigateToMock).toHaveBeenCalledWith("/workspace/adr/adr-42");
  });

  it("shows a remove button with an accessible label", () => {
    const wrapper = mountAdrCard({
      id: "adr-1",
      title: "Use PostgreSQL for persistence",
      status: "draft",
      updatedAt: "2026-06-16T10:00:00Z",
    });

    const removeButton = wrapper.get('[aria-label="Remove ADR"]');
    expect(removeButton.exists()).toBe(true);
  });

  it("does not navigate when the remove button is clicked", async () => {
    const wrapper = mountAdrCard({
      id: "adr-42",
      title: "Cache strategy",
      status: "proposed",
      updatedAt: "2026-06-16T12:00:00Z",
    });

    await wrapper.get('[aria-label="Remove ADR"]').trigger("click");

    expect(navigateToMock).not.toHaveBeenCalled();
  });

  it("emits remove with the card id when removal is confirmed", async () => {
    const wrapper = mountAdrCard({
      id: "adr-42",
      title: "Cache strategy",
      status: "proposed",
      updatedAt: "2026-06-16T12:00:00Z",
    });

    await wrapper.get('[data-testid="confirm-remove"]').trigger("click");
    await flushPromises();

    expect(wrapper.emitted("remove")).toEqual([["adr-42"]]);
  });
});
