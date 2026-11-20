import { chromium } from "playwright-core";

const base = (process.env.CHECK_CRM_URL ?? "http://127.0.0.1:4173").replace(/\/$/, "");
const browser = await chromium.launch({
  executablePath: process.env.CHECK_UI_CHROME,
  headless: true,
  args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
}
page.on("pageerror", (error) => console.log("PAGEERROR", error.message));

// 1. Required-field validation.
await page.goto(`${base}/lead/new`);
await page.getByTestId("record-save").click();
await page.waitForTimeout(200);
check(
  "required fields block the save",
  (await page.getByTestId("form-error").innerText()).includes("obbligatori"),
);

// 2. Company auto-link for a contact with one relationship.
await page.getByTestId("lead-contact").selectOption("p1");
await page.waitForTimeout(150);
check(
  "single-company contact auto-fills Azienda",
  (await page.getByTestId("lead-company").inputValue()) === "c1",
);
check("auto-filled Azienda is locked", await page.getByTestId("lead-company").isDisabled());

// 3. Uniqueness (Contatto, Iniziativa).
await page.getByTestId("lead-initiative").selectOption("i6");
await page.waitForTimeout(150);
check("duplicate pair shows the warning", (await page.getByTestId("duplicate-warning").count()) === 1);
await page.getByTestId("lead-initiative").selectOption("i2");
await page.waitForTimeout(150);
check("a different initiative clears the warning", (await page.getByTestId("duplicate-warning").count()) === 0);

// 4. Save creates the record and reports the saved state.
await page.getByTestId("record-save").click();
await page.waitForURL(/\/lead\/L-\d+/);
await page.getByTestId("save-state").filter({ hasText: "Salvataggio completato" }).waitFor({ timeout: 5000 });
check("save creates the lead", /\/lead\/L-\d+$/.test(page.url()), page.url().split("/").pop());
check("save state reads Salvataggio completato", true);

// 5. Closing-date hook: a closed status sets Data chiusura.
await page.getByRole("button", { name: "Modifica campi intestazione" }).click();
await page.getByTestId("header-status").selectOption("servizio_concluso");
await page.getByTestId("header-apply").click();
await page.getByTestId("record-save").click();
await page.waitForTimeout(400);
const closed = await page.getByTestId("closed-at").innerText();
check("closed status sets Data chiusura", /^\d{2}\/\d{2}\/\d{4}/.test(closed), closed);

// 6. The closed lead leaves the open view.
await page.goto(`${base}/`);
await page.waitForTimeout(500);
let rows = await page.locator("tbody tr").count();
check("open view drops the closed lead", rows === 42, `${rows} rows`);

// 7. Reassignment: the lead leaves the old owner's personal open view.
await page.goto(`${base}/lead/L-9020`);
await page.getByRole("button", { name: "Modifica campi intestazione" }).click();
await page.getByTestId("header-owner").selectOption("luca");
await page.getByTestId("header-apply").click();
await page.getByTestId("record-save").click();
await page.waitForTimeout(400);
check("record header shows the new owner", (await page.locator("body").innerText()).includes("Luca Bianchi"));
await page.goto(`${base}/`);
await page.waitForTimeout(500);
rows = await page.locator("tbody tr").count();
check("reassigned lead leaves the personal open view", rows === 41, `${rows} rows`);

// 8. View selector: Lead chiusi shows closed statuses.
await page.getByRole("button", { name: /Lead personali aperti/ }).click();
await page.getByRole("button", { name: "Lead chiusi", exact: true }).click();
await page.waitForTimeout(400);
const closedView = await page.locator("table").innerText();
check(
  "Lead chiusi view renders closed records",
  closedView.includes("Servizio concluso") && closedView.includes("Contratto concluso"),
);

// 9. Columns panel: showing Provincia (Azienda) adds the column.
await page.getByRole("button", { name: "Modifica colonne" }).click();
await page.getByLabel("Provincia (Azienda)").check();
await page.waitForTimeout(200);
check("column picker adds Provincia (Azienda)", (await page.locator("table").innerText()).includes("PROVINCIA (AZIENDA)"));

const failed = results.filter((entry) => !entry.ok);
console.log(`\n${results.length - failed.length}/${results.length} interaction checks passed`);
await browser.close();
process.exit(failed.length === 0 ? 0 : 1);
