import { test, expect } from "@playwright/test";

/**
 * End-to-end coverage of the critical user flow:
 *
 *   GitHub URL -> Analyze -> Progress -> Repository Dashboard ->
 *   Architecture Graph -> Code Explorer -> Insights -> Impact Analysis
 *
 * Runs against the REAL stack (frontend + backend + Postgres + a real
 * GitHub clone) -- see playwright.config.ts for prerequisites. Uses
 * pypa/sampleproject specifically because it's tiny (12 files), so the
 * clone + analysis step stays fast and the test doesn't depend on network
 * variance for a large repo.
 */

const SAMPLE_REPO = "https://github.com/pypa/sampleproject";

test("analyze a repository and walk every tab through to impact analysis", async ({ page }) => {
  test.setTimeout(150_000);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Understand any/i })).toBeVisible();

  await page.getByLabel("GitHub repository URL").fill(SAMPLE_REPO);
  await page.getByRole("button", { name: "Analyze Repository" }).click();

  // Analysis can be near-instant (incremental reuse of a prior run) or take
  // a while (fresh clone) -- wait generously for the Overview redirect
  // rather than asserting on the progress checklist's exact timing.
  await page.waitForURL(/\/repository\/[0-9a-f-]+$/, { timeout: 120_000 });

  // --- Repository Overview ---
  await expect(page.getByRole("heading", { name: "pypa/sampleproject" })).toBeVisible();
  await expect(page.getByText("Files", { exact: true })).toBeVisible();
  await expect(page.getByText("Lines of code")).toBeVisible();
  await expect(page.getByText("Symbols", { exact: true })).toBeVisible();
  await expect(page.getByText("Dependency edges")).toBeVisible();

  const repositoryUrl = page.url();
  const repositoryId = repositoryUrl.match(/\/repository\/([0-9a-f-]+)$/)?.[1];
  expect(repositoryId).toBeTruthy();

  // --- Code Explorer ---
  await page.getByRole("link", { name: "Code Explorer" }).click();
  await page.waitForURL(/\/explorer$/);
  await expect(page.getByLabel("Search symbols")).toBeVisible();

  const fileButtons = page.locator(".wx-tree__file");
  await expect(fileButtons.first()).toBeVisible();
  const fileCount = await fileButtons.count();
  expect(fileCount).toBeGreaterThan(0);

  // Click through files until one with a resolvable symbol (a "View
  // impact" link) turns up -- small repo, cheap to just try them all
  // rather than depending on knowing sampleproject's exact file layout.
  let viewImpactLink = page.getByRole("link", { name: "View impact" }).first();
  let found = false;
  for (let i = 0; i < fileCount; i++) {
    await fileButtons.nth(i).click();
    if (await viewImpactLink.isVisible().catch(() => false)) {
      found = true;
      break;
    }
  }
  expect(found, "expected at least one file to expose a symbol with a resolvable impact link").toBe(true);

  // --- Architecture Graph ---
  await page.getByRole("link", { name: "Architecture Graph" }).click();
  await page.waitForURL(/\/graph$/);
  await expect(page.getByText(/Click a node to highlight/)).toBeVisible();
  await expect(page.locator(".react-flow")).toBeVisible();
  await expect(page.getByPlaceholder("Filter files by path...")).toBeVisible();

  // --- Insights ---
  await page.getByRole("link", { name: "Insights" }).click();
  await page.waitForURL(/\/insights$/);
  await expect(page.getByRole("heading", { name: "Circular dependencies" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fan-in / fan-out" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Large files" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Isolated files" })).toBeVisible();

  // --- Impact Analysis (reached from the Explorer tab found above) ---
  await page.getByRole("link", { name: "Code Explorer" }).click();
  await page.waitForURL(/\/explorer$/);
  for (let i = 0; i < fileCount; i++) {
    await fileButtons.nth(i).click();
    if (await viewImpactLink.isVisible().catch(() => false)) break;
  }
  await viewImpactLink.click();
  await page.waitForURL(/\/impact\/[0-9a-f-]+$/);

  await expect(page.getByRole("heading", { name: "Change Impact" })).toBeVisible();
  await expect(page.getByText("Direct callers").first()).toBeVisible();
  await expect(page.getByText("Affected symbols").first()).toBeVisible();
  await expect(page.getByText("Affected files").first()).toBeVisible();
  await expect(page.getByText("Affected tests").first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Back to Code Explorer/ })).toBeVisible();

  // --- Repository history on the landing page picks this analysis back up ---
  await page.goto("/");
  await expect(page.getByRole("link", { name: /pypa\/sampleproject/ }).first()).toBeVisible();
});

test("an unknown route renders the 404 page with a way back", async ({ page }) => {
  await page.goto("/this/route/does/not/exist");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await page.getByRole("link", { name: /Back to Code Intelligence/ }).click();
  await expect(page.getByRole("heading", { name: /Understand any/i })).toBeVisible();
});
