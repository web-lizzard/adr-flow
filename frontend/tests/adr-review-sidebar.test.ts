import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AdrReviewSidebar from "../app/components/adr/AdrReviewSidebar.vue";

describe("AdrReviewSidebar", () => {
  it("renders review content when open and emits close", async () => {
    const wrapper = mount(AdrReviewSidebar, {
      props: {
        open: true,
        annotations: [
          {
            kind: "missing_section",
            message: "Add a Decision section",
          },
        ],
        sectionRatings: [
          { section: "Context", score: 2, feedback: "Needs more detail." },
        ],
        reviewError: null,
        status: "after_review",
      },
    });

    expect(wrapper.find("aside").exists()).toBe(true);
    expect(wrapper.text()).toContain("Add a Decision section");
    expect(wrapper.text()).toContain("Needs more detail.");

    await wrapper
      .get("button[aria-label='Close review sidebar']")
      .trigger("click");
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("renders nothing when closed", () => {
    const wrapper = mount(AdrReviewSidebar, {
      props: {
        open: false,
        annotations: [],
        sectionRatings: [],
        reviewError: null,
        status: "after_review",
      },
    });

    expect(wrapper.find("aside").exists()).toBe(false);
  });
});
