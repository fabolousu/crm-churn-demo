# Prompt for the DeepSeek harness: CRM redesign, Phases 1 and 2

Paste everything below the line into the harness on the dsh server.

---

You are continuing work on the repo `fabolousu/crm-churn-demo`. Your job is the **design phase**
of the CRM redesign: build the design system in Google Stitch, then design the screens one at a
time with the owner approving each. You do **not** touch `web/` in this task.

## 0. Before anything

1. `git pull` on `main` (or check out branch `lane/design-phase0` if it is not merged yet). Work on a
   new branch `lane/design-phase1`.
2. Check that the Stitch MCP server is connected (`stitch_find` / `stitch_get` must respond). If it
   is not, **stop and tell the owner**: the API key for Stitch on this server is still an open
   question. Do not try to work around it.
3. Never use em dashes or en dashes in any file, commit message or reply. Use a colon or a comma.

## 1. What the product is (read these, in this order)

| File | Why |
|---|---|
| `README.md`, `docs/DECISIONS.md`, `docs/LABEL.md` | The goal: a **simplified** rebuild of the agency's Dynamics 365 sales CRM plus an AI module, **Previsioni**, that gives every open lead a **win probability**, explains it with three SHAP drivers, and ranks the pipeline by expected value. The model target is **lead win**. Churn is not modelled; it only appears as a dormancy flag on the company page. Do not change this |
| `docs/SITE_REQUIREMENTS_AND_FEATURES.md` | What is live today, the site map, requirement IDs (S, L, C, B, P, N) and priorities P0/P1/P2 |
| `docs/UI_FEATURE_INVENTORY.md`, `docs/CRM_UI_STATUS.md` | Which spec rows are P0 and which are named gaps |
| `crm design/design refs/CRM_Sales_Module_Rebuild_Spec.md` | The full functional spec of the legacy CRM |
| `crm design/design refs/SCREENSHOT_AUDIT.md` | What the spec gets wrong or misses, checked against 40 legacy screenshots, plus an index of the screenshots by screen type |
| `crm design/DESIGN_INPUTS.md` | Brand tokens, the never-list, open decisions |
| `crm design/.stitch/metadata.json` | Stitch project `3133723532266431010` and its design system "Promos Sales Fresh" |

**Simplification means:** keep every P0 behaviour and business rule, but cut Dynamics clutter.
One command bar with the 4 to 6 actions a salesperson uses, the rest in an overflow menu.
No duplicated controls. Previsioni is part of the CRM, not a separate app: the win probability
and its top driver should be visible where the lead is worked (grid column, lead header), with the
full explanation one click away.

**The three kinds of reference, and what each is for:**
- `crm design/design refs/crm must have features/`: **what** to build. Not how it looks.
- Promos Italia website screenshots, fonts file, palettes: **brand**. The CRM must look like a
  Promos Italia product (blue `#005EB8`, ink `#19242E`, green `#88E771`, forma-djr-text, square
  corners).
- `www.pipedrive.com_it_edited.png`: **UX patterns** only (pipeline view by status, next-step and
  follow-up reminders, inline assistant, fewer clicks). Never its colors or layout.

## 2. Step A: bring the spec up to date

Apply every row of section 3 in `SCREENSHOT_AUDIT.md` to `CRM_Sales_Module_Rebuild_Spec.md`:
fix the contradictions (C1 to C6) in place, add the missing items (M1 to M17) in the section each
row names. Mark each change `[from screenshots]`. Do not rewrite sections the audit does not touch.
Commit: `docs(spec): apply screenshot audit`.

## 3. Step B: Phase 1, design system (Stitch skills, in this order)

1. **`extract-design-md` on `web/`**: record today's design as the baseline being replaced. Save it as
   `crm design/DESIGN.baseline.md`.
2. **`taste-design`**, then edit by hand: write `crm design/DESIGN.md` from `DESIGN_INPUTS.md` and the
   reference images. Remove everything the skill adds for landing pages: constant motion, uneven or
   asymmetric layouts, hero sections, decorative gradients. A CRM is a work tool. Put the never-list
   from `DESIGN_INPUTS.md` section 2 into `DESIGN.md` verbatim. Use the recommendations in
   `DESIGN_INPUTS.md` section 3 for D1 to D3 unless the owner says otherwise.
3. **`manage-design-system`**: update "Promos Sales Fresh" in project `3133723532266431010` to match
   `DESIGN.md` (font, accent `#005EB8`, roundness at most 4px, light mode). Update
   `crm design/.stitch/metadata.json`.
4. **`site-md`**: turn `docs/SITE_REQUIREMENTS_AND_FEATURES.md` plus the updated spec into
   `crm design/SITE.md`: the screen list with priorities and, for each screen, the exact fields,
   Italian labels and states it needs.

Commit after each step. Then **stop and show the owner** `DESIGN.md` and the updated design system
before Phase 2.

## 4. Step C: Phase 2, screens one at a time

Order: `Lead personali aperti` (the most used grid), `Scheda Lead`, Previsioni queue, Lead 360,
Lever, Act, Portfolio.

For each screen:
1. **`upload-to-stitch`**: upload 1 or 2 reference images, chosen from the screen-type index in
   `SCREENSHOT_AUDIT.md` section 2 (for features) and one Promos screenshot (for brand).
2. **`enhance-prompt`**: turn the screen's rows in `SITE.md` into a precise prompt with real fields,
   real Italian labels and realistic Italian seed values (see `web/src/crm/seed.ts`).
3. **`generate-design`** with **3 variants**. Show them to the owner, who picks one. Then 1 or 2
   rounds of edits on the owner's feedback.
4. Design the **empty, loading and error** states of the screen in Stitch too.
5. Check the result against the never-list, item by item, and write the check into
   `crm design/screens/<screen>.md` (pass / fail per rule, and the Stitch screen ID).
6. Save the HTML and PNG under `crm design/.stitch/designs/`, update `metadata.json`, commit, and
   wait for the owner's approval before the next screen.

**Do not use `stitch-loop`.** It generates screens with nobody choosing, which is exactly where the
generic AI look comes from.

## 5. Rules

- Never pick a variant or approve a screen yourself. The owner decides.
- Never invent fields, statuses or numbers. Fields come from the spec, values from the seed or
  `ml/artifacts/metrics.json`.
- Keep the Previsioni numbers honest: probability, three drivers, expected value. No decorative
  charts.
- Do not edit `web/`, `api/`, `ml/` or `data/`. The build phase (Phase 3) is a separate task.
- Open a PR at the end with the list of screens, their Stitch IDs and the never-list checks.
