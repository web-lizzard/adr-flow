import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AdrReviewAnnotations from "../app/components/adr/AdrReviewAnnotations.vue";
import type { ReviewAnnotation, ReviewError } from "../app/stores/adr";

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
};

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

  it("shows an empty state when after_review has no annotations", () => {
    const wrapper = mount(AdrReviewAnnotations, {
      props: {
        annotations: [],
        reviewError: null,
        status: "after_review",
      },
    });

    expect(wrapper.text()).toContain("No review annotations");
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
  });
});
