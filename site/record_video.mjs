// Screen-records the live Studio demo into site/media/studio-demo.webm for the landing page.
// Needs @playwright/test, so copy this file into studio/ and run it there: node record_video.mjs
import { chromium } from "@playwright/test";

const OUT = process.env.OUT ?? "video";
const BASE = "https://etalon-studio.netlify.app/studio/";
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  recordVideo: { dir: OUT, size: { width: 1280, height: 720 } },
  locale: "en-US",
});
const page = await context.newPage();
const pause = (ms) => page.waitForTimeout(ms);
await page.goto(BASE);
await page.getByRole("link", { name: "phc_waveguide.py" }).waitFor();
await pause(2500);
await page.getByRole("link", { name: "phc_waveguide.py" }).click();
await page.getByRole("link", { name: "Setup" }).click();
await page.getByRole("img", { name: "The simulation in 3D" }).waitFor({ timeout: 30000 });
await pause(4000);
await page.getByRole("radio", { name: "Slice" }).click();
await pause(3000);
await page.getByRole("button", { name: "Run" }).click();
await page.getByText("The run finished.").waitFor({ timeout: 60000 });
await pause(2500);
await page.getByRole("link", { name: "Open results" }).click();
await page.getByRole("img", { name: /on monitor/ }).waitFor({ timeout: 30000 });
await pause(4000);
await page.getByRole("tab", { name: "Spectra" }).click();
await pause(4000);
await context.close();
await browser.close();
console.log("recorded into", OUT);
