import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AdrReviewAnnotations from "../app/components/adr/AdrReviewAnnotations.vue";
import type {
  ReviewAnnotation,
  ReviewError,
  SectionRating,
} from "../app/stores/adr";

const sampleAnnotations: ReviewAnnotation[] = [
  {
    kind: "missing_section",
    message: "Add a Consequences section",
    location: "## Consequences",
    suggestion: "Describe trade-offs",
  },
  {
    kind: "inconsistency",
    message: "Context contradicts the decision",
    location: "## Context",
  },
  {
    kind: "conciseness",
    message: "Options section is verbose",
    suggestion: "Trim bullet points",
  },
];

const sampleError: ReviewError = {
  source_event_id: "evt-1",
  code: "validation_failed",
  message: "Review output was invalid",
  failed_at: "2026-06-16T12:00:00Z",
  kind: "adr_review_failed_error",
};

const sampleRatings: SectionRating[] = [
  { section: "Context", score: 0, feedback: "" },
  { section: "Options", score: 3, feedback: "Adequate alternatives listed." },
  { section: "Decision", score: 4, feedback: "Clear choice documented." },
  { section: "Status", score: 2, feedback: "Status is vague." },
  { section: "Consequences", score: 1, feedback: "Minimal trade-off detail." },
];

describe("AdrReviewAnnotations", () => {
  it("renders grouped annotations by kind with message, location, and suggestion", () => {
    const wrapper = mount(AdrReviewAnnotations, {
      props: {
        annotations: sampleAnnotations,
        reviewError: null,
      },
    });

    expect(wrapper.text()).toContain("Missing section");
    expect(wrapper.text()).toContain("Add a Consequences section");
    expect(wrapper.text()).toContain("## Consequences");
    expect(wrapper.text()).toContain("Describe trade-offs");

    expect(wrapper.text()).toContain("Inconsistency");
    expect(wrapper.text()).toContain("Context contradicts the decision");

    expect(wrapper.text()).toContain("Conciseness");
    expect(wrapper.text()).toContain("Trim bullet points");
  });

  it("shows an empty state when after_review has no annotations or ratings", () => {
    const wrapper = mount(AdrReviewAnnotations, {
      props: {
        annotations: [],
        sectionRatings: [],
        reviewError: null,
        status: "after_review",
      },
    });

    expect(wrapper.text()).toContain("No review annotations");
  });

  it("does not show empty state when after_review has section ratings only", () => {
    const wrapper = mount(AdrReviewAnnotations, {
      props: {
        annotations: [],
        sectionRatings: sampleRatings,
        reviewError: null,
        status: "after_review",
      },
    });

    expect(wrapper.text()).not.toContain("No review annotations");
    expect(wrapper.text()).toContain("Section ratings");
    expect(wrapper.text()).toContain("Context");
    expect(wrapper.text()).toContain("0/5");
    expect(wrapper.text()).toContain("Adequate alternatives listed.");
  });

  it("renders section ratings below annotation groups", () => {
    const wrapper = mount(AdrReviewAnnotations, {
      props: {
        annotations: sampleAnnotations,
        sectionRatings: sampleRatings,
        reviewError: null,
      },
    });

    expect(wrapper.text()).toContain("Missing section");
    expect(wrapper.text()).toContain("Section ratings");
    expect(wrapper.text()).toContain("4/5");
    expect(wrapper.text()).toContain("Clear choice documented.");
  });

  it("shows recoverable review error metadata", () => {
    const wrapper = mount(AdrReviewAnnotations, {
      props: {
        annotations: null,
        reviewError: sampleError,
      },
    });

    expect(wrapper.text()).toContain("Review failed");
    expect(wrapper.text()).toContain("Review output was invalid");
    expect(wrapper.text()).toContain(
      "The review could not finish. You can try again.",
    );
    expect(
      wrapper.findAll("button").find((button) => button.text() === "Try again"),
    ).toBeDefined();
  });

  it("shows retry guidance and Try again for retryable_internal_error", async () => {
    const wrapper = mount(AdrReviewAnnotations, {
      props: {
        annotations: null,
        reviewError: {
          ...sampleError,
          kind: "retryable_internal_error",
        },
        retrying: false,
      },
    });

    expect(wrapper.text()).toContain(
      "The review could not finish. You can try again.",
    );
    const retryButton = wrapper
      .findAll("button")
      .find((button) => button.text() === "Try again");
    expect(retryButton).toBeDefined();
    await retryButton!.trigger("click");
    expect(wrapper.emitted("retry")).toHaveLength(1);
  });

  it("shows admin placeholder and hides Try again for internal_error", () => {
    const wrapper = mount(AdrReviewAnnotations, {
      props: {
        annotations: null,
        reviewError: {
          ...sampleError,
          kind: "internal_error",
        },
      },
    });

    expect(wrapper.text()).toContain(
      "Something went wrong on our side. Contact your administrator if this keeps happening.",
    );
    expect(
      wrapper.findAll("button").find((button) => button.text() === "Try again"),
    ).toBeUndefined();
  });
});
