import { test, expect } from "@playwright/test";

test.describe("Core User Flows", () => {
  test("should load the dashboard page", async ({ page }) => {
    // The auth flow might redirect to login if not authenticated,
    // but we can check if it at least loads the app frame.
    await page.goto("/");

    // Expect the title to have OpsLens
    await expect(page).toHaveTitle(/OpsLens/);

    // Check if the logo/brand is visible
    const brand = page.locator("text=OpsLens").first();
    await expect(brand).toBeVisible();
  });

  test.skip("should have a command palette trigger (requires auth)", async ({
    page,
  }) => {
    await page.goto("/");

    // Wait for the app to be fully loaded (React hydrated)
    await expect(page.locator("text=OpsLens").first()).toBeVisible();

    // Test the global command palette by clicking the search button
    await page.getByText("Search pages…").click();

    // The palette should appear
    const palette = page.getByRole("dialog");
    await expect(palette).toBeVisible({ timeout: 5000 });
  });
});
