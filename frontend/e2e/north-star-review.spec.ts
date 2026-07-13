import { expect, test } from "./fixtures";
import {
  COMPLETE_ADR_CONTENT,
  createAdr,
  seedAdrContent,
  uniqueTitle,
} from "./helpers";

// Risk anchor: context/foundation/test-plan.md §2 risks #1, #2, #4
// Provenance: context/foundation/test-plan.md §1 North star, §3 Phase 3
test("north-star review flow reaches proposed with deterministic feedback", async ({
  page,
  request,
}) => {
  // Step 1: Setup via API (create ADR + deterministic reviewable content).
  const { id } = await createAdr(request, uniqueTitle("E2E Review"));
  await seedAdrContent(request, id, COMPLETE_ADR_CONTENT);

  // Step 2-3: Open ADR editor and confirm draft + review CTA.
  await page.goto(`/workspace/adr/${id}`);
  const publishForReviewButton = page.getByRole("button", {
    name: "Publish for review",
  });
  await expect(publishForReviewButton).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Draft", { exact: true })).toBeVisible();

  // Step 4-6: Submit for review and wait for Review feedback sidebar.
  await publishForReviewButton.click();

  const reviewSidebar = page.getByRole("complementary", {
    name: "Review feedback",
  });
  await expect(reviewSidebar).toBeVisible({ timeout: 15_000 });

  // Step 7: Confirm after-review state is actionable.
  await expect(page.getByText("After review")).toBeVisible();
  await expect(page.getByRole("button", { name: "Publish" })).toBeVisible();
  await expect(page.getByText(/Edit based on review feedback/i)).toBeVisible();

  // Step 8: Assert deterministic section ratings and feedback.
  await expect(
    reviewSidebar.getByRole("heading", { name: "Section ratings" }),
  ).toBeVisible();
  await expect(reviewSidebar.getByText("Context 3/5")).toBeVisible();
  await expect(reviewSidebar.getByText("Options 2/5")).toBeVisible();
  await expect(reviewSidebar.getByText("Decision 2/5")).toBeVisible();
  await expect(reviewSidebar.getByText("Status 2/5")).toBeVisible();
  await expect(reviewSidebar.getByText("Consequences 3/5")).toBeVisible();
  await expect(
    reviewSidebar.getByText("Fake review for Context section."),
  ).toBeVisible();
  await expect(
    reviewSidebar.getByText("Fake review for Options section."),
  ).toBeVisible();
  await expect(
    reviewSidebar.getByText("Fake review for Decision section."),
  ).toBeVisible();
  await expect(
    reviewSidebar.getByText("Fake review for Status section."),
  ).toBeVisible();
  await expect(
    reviewSidebar.getByText("Fake review for Consequences section."),
  ).toBeVisible();

  // Step 9: Assert deterministic inconsistency annotation details.
  await expect(
    reviewSidebar.getByRole("heading", { name: "Inconsistency" }),
  ).toBeVisible();
  await expect(
    reviewSidebar.getByText("Status may not reflect the recorded decision."),
  ).toBeVisible();
  await expect(reviewSidebar.getByText("## Status")).toBeVisible();

  // Step 10-11: Confirm editability in after_review and change title.
  const titleInput = page.getByRole("textbox", { name: "Title", exact: true });
  await expect(titleInput).toBeEnabled();
  await expect(page.getByRole("button", { name: "bold" })).toBeVisible();

  const reviewedTitle = uniqueTitle("E2E Review Reviewed");
  await titleInput.fill(reviewedTitle);
  await page.getByRole("heading", { name: "Edit ADR" }).click();

  // Step 12-13: Publish and confirm proposed end-state.
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByText("Proposed", { exact: true })).toBeVisible();
});
