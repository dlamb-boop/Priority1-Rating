import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const outDir = "/opt/cursor/artifacts";
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({
  channel: "chrome",
  headless: true,
  args: ["--disable-dev-shm-usage"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 1 });

await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
await page.getByRole("heading", { name: "Quote freight without leaving the desk." }).waitFor();
await page.locator("#load-sample").click();
await page.screenshot({ path: path.join(outDir, "screenshot_quote_form.png"), fullPage: true });

const classValue = await page.locator(".item-card select").first().inputValue();

await page.locator("#get-rates").click();
await page.locator("#rates-table").waitFor();
await page.locator("#rates-panel").screenshot({ path: path.join(outDir, "screenshot_rates.png") });

const internalVisible = await page.locator(".internal").count();

const [download] = await Promise.all([
  page.waitForEvent("download"),
  page.locator("#download-pdf").click(),
]);
const pdfPath = path.join(outDir, "sample_freight_quote.pdf");
await download.saveAs(pdfPath);

await page.getByRole("tab", { name: "Truckload" }).click();
await page.locator("#get-rates").click();
await page.getByText("Truckload option 1").waitFor();
const tlWarning = await page.locator(".warning").first().innerText();

await page.setViewportSize({ width: 390, height: 844 });
await page.getByRole("tab", { name: "LTL" }).click();
await page.screenshot({ path: path.join(outDir, "screenshot_form_mobile.png"), fullPage: false });

console.log(JSON.stringify({ classValue, internalVisible, pdfPath, tlWarning, downloadName: download.suggestedFilename() }, null, 2));
await browser.close();
