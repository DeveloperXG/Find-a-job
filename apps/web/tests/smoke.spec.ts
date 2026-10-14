import { expect, test } from "@playwright/test";

test("shell renders with sidebar, search and bell", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/feed$/);
  const nav = page.getByRole("navigation", { name: "Main" });
  for (const label of ["Feed", "Pipeline", "Resumes", "Companies", "Runs", "Settings"]) {
    await expect(nav.getByRole("link", { name: label })).toBeVisible();
  }
  await expect(page.getByRole("searchbox", { name: "Search jobs" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Notifications" })).toBeVisible();
});

test("sidebar navigation marks the current page", async ({ page }) => {
  await page.goto("/feed?page=2");
  await page.getByRole("link", { name: "Feed" }).click();
  await expect(page.getByRole("link", { name: "Feed" })).toHaveAttribute("aria-current", "page");
});

test("feed table renders mocked rows and paginates", async ({ page }) => {
  await page.goto("/feed");
  await expect(page.getByRole("row")).toHaveCount(51); // header + 50
  await page.getByRole("link", { name: "Next" }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByText("Page 2 of 10")).toBeVisible();
});

test("feed renders 500 rows", async ({ page }) => {
  await page.goto("/feed?size=500");
  await expect(page.getByRole("row")).toHaveCount(501);
});

test("dark-mode toggle swaps tokens", async ({ page }) => {
  await page.goto("/feed");
  const bg = () => page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--bg").trim());
  const before = await bg();
  await page.getByRole("button", { name: "Toggle dark mode" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  expect(await bg()).not.toBe(before);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
});
