// SPDX-FileCopyrightText: 2026 Edgar Fuentes Perea <efuentesp@gmail.com>
// SPDX-License-Identifier: Apache-2.0

import { test, expect } from "@playwright/test";
import { loginToWebUI } from "./helpers";

test.describe("Sandbox telemetry dashboard", () => {
  test("admin dashboard exposes the Sandboxes tab with KPIs", async ({
    page,
  }) => {
    await loginToWebUI(page);
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("tab", { name: "Sandboxes" })).toBeVisible({
      timeout: 10_000,
    });
    await page.getByRole("tab", { name: "Sandboxes" }).click();

    await expect(page.getByText("Total runs")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Timeouts")).toBeVisible();
    await expect(page.getByText("OOM kills")).toBeVisible();
    await expect(page.getByText("p95 latency")).toBeVisible();
  });
});
