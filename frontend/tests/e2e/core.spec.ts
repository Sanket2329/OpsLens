import { test, expect } from '@playwright/test';

test.describe('Core User Flows', () => {
  test('should load the dashboard page', async ({ page }) => {
    // The auth flow might redirect to login if not authenticated, 
    // but we can check if it at least loads the app frame.
    await page.goto('/');
    
    // Expect the title to have OpsLens
    await expect(page).toHaveTitle(/OpsLens/);
    
    // Check if the logo/brand is visible
    const brand = page.locator('text=OpsLens').first();
    await expect(brand).toBeVisible();
  });

  test('should have a command palette trigger', async ({ page }) => {
    await page.goto('/');
    
    // Test the global command palette
    await page.keyboard.press('Meta+K'); // Mac
    
    // The palette should appear
    const palette = page.locator('[cmdk-dialog]');
    await expect(palette).toBeVisible({ timeout: 5000 }).catch(async () => {
      // Fallback for Windows/Linux
      await page.keyboard.press('Control+K');
      await expect(palette).toBeVisible();
    });
  });
});
