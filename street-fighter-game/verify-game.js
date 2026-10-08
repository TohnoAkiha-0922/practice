const path = require("path");
const { pathToFileURL } = require("url");
const { chromium } = require("playwright");

(async () => {
  const gameUrl = pathToFileURL(path.resolve(__dirname, "index.html")).href;
  const shot = path.resolve(__dirname, "screenshot.png");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  const errors = [];

  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console ${message.type()}: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto(gameUrl);
  await page.waitForLoadState("networkidle");
  await page.keyboard.down("d");
  await page.waitForTimeout(250);
  await page.keyboard.up("d");
  await page.keyboard.press("j");
  await page.waitForTimeout(350);
  await page.keyboard.press("k");
  await page.waitForTimeout(500);

  const result = await page.evaluate(() => {
    const canvas = document.querySelector("#game");
    const context = canvas.getContext("2d");
    const data = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let nonBlank = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i] || data[i + 1] || data[i + 2]) nonBlank += 1;
    }
    return {
      canvasWidth: canvas.width,
      canvasHeight: canvas.height,
      nonBlank,
      playerHealth: document.querySelector("#playerHealth").style.width,
      enemyHealth: document.querySelector("#enemyHealth").style.width,
      timer: document.querySelector("#timerText").textContent,
    };
  });

  await page.screenshot({ path: shot, fullPage: true });
  await browser.close();

  if (errors.length) throw new Error(errors.join("\n"));
  if (result.nonBlank < 1000) throw new Error("Canvas did not render enough nonblank pixels.");
  console.log(JSON.stringify(result, null, 2));
})();
