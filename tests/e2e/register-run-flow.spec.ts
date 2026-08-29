import { expect, test } from "@playwright/test";

/**
 * The golden path this whole app exists to support: register, build a
 * project, run code, and see the result — both live and later in history.
 * Runs against a real docker-compose stack (real Postgres, real Redis, a
 * real Docker sandbox container), not mocks, so a pass here means the whole
 * pipeline actually works end to end.
 */
test("register, create project, run code, and see output and history", async ({ page }) => {
  const email = `e2e-${Date.now()}@codeforge.dev`;
  const password = "e2etestpassword123";

  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard/);

  await page.getByRole("button", { name: "New project" }).click();
  await page.getByLabel("Name").fill("E2E Project");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]+$/);

  await page.getByRole("button", { name: "New file" }).click();
  const fileNameInput = page.getByPlaceholder("file.py");
  await fileNameInput.fill("main.py");
  await fileNameInput.press("Enter");
  await expect(page.getByText("main.py", { exact: true }).first()).toBeVisible();

  await page.locator(".monaco-editor").click();
  // insertText (not keyboard.type): typing character-by-character triggers
  // Monaco's auto-closing brackets/quotes, which fights the keystrokes for
  // the closing quote/paren we're also typing and corrupts the result (e.g.
  // `print("hello")` becomes `print("") hello")`). insertText inserts the
  // whole string at once, like a paste, bypassing that per-keystroke logic.
  await page.keyboard.insertText(['print("hello from e2e")', "print(2 + 2)"].join("\n"));

  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Saved")).toBeVisible();

  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.getByText("hello from e2e")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Execution successful")).toBeVisible({ timeout: 20_000 });

  await page.getByRole("link", { name: "History" }).click();
  await expect(page).toHaveURL(/\/executions$/);
  await expect(page.getByText("success", { exact: false }).first()).toBeVisible();
});
