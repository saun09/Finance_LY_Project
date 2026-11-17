// Builds allocation_validation.pptx: how the asset-allocation engine is validated.
// Numbers come from running backend/app/services/allocation.py for tiers 1-5
// and comparing each result against 20,000 random portfolios within the tier's limits.
// Run: node research_artifacts/results/allocation_validation_deck.js

const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(path.join(
  process.env.USERPROFILE,
  ".claude/skills/synced/d59f10e2-5479-41a0-99b0-bf99f56c5cfd_2c783610-cbd1-4bfb-be65-53f0b3bd78a7/pptx/scripts/apply_theme.js"
));

const OUT = path.join(__dirname, "allocation_validation.pptx");

const THEME = {
  name: "Allocation Validation",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2A41", lt1: "FFFFFF", dk2: "475569", lt2: "EEF3F7",
    accent1: "0F766E", accent2: "D97706", accent3: "2A78D6",
    accent4: "94A3B8", accent5: "7C3AED", accent6: "B91C1C",
    hlink: "0F766E", folHlink: "475569",
  },
};
const HEX = THEME.colors;
// Asset-class colours (cash, debt, equity, real assets, alternatives)
const ASSET_COLORS = ["94A3B8", "2A78D6", "0F766E", "D97706", "7C3AED"];

const TIERS = ["Tier 1", "Tier 2", "Tier 3", "Tier 4", "Tier 5"];
const SPLIT = { // % per tier, from compute_target_allocation()
  Cash: [30, 15, 8, 5, 2],
  Debt: [50, 50, 45, 30, 20],
  Equity: [15, 25, 31, 44, 56],
  "Real assets": [5, 8, 12, 14, 14],
  Alternatives: [0, 2, 4, 7, 8],
};
const RET = [7.1, 8.1, 8.7, 9.6, 10.3];
const VOL = [4.4, 6.5, 7.9, 10.6, 13.0];
const SHARPE = [0.244, 0.322, 0.34, 0.335, 0.33];
const EQ_RANGE = ["5–15", "15–25", "28–40", "42–55", "55–72"];

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "Validating the Asset Allocation Engine";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: "DARK",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.5, w: 8.8, h: 1.4, fontFace: THEME.headFontFace, fontSize: 40, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.05, w: 8.8, h: 1.2, fontFace: THEME.bodyFontFace, fontSize: 18, color: "CBD5E1", valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  slideNumber: { x: 9.2, y: 5.2, w: 0.5, h: 0.3, fontFace: THEME.bodyFontFace, fontSize: 10, color: "94A3B8", align: "right" },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.75, fontFace: THEME.headFontFace, fontSize: 26, bold: true, color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
  ],
});

function contentSlide(title, section) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(title, { placeholder: "title" });
  return s;
}

function card(slide, x, y, w, h, name, fill = C.background2) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08, objectName: name });
}

function numberBadge(slide, x, y, n, fill) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.42, h: 0.42, fill: { color: fill }, line: { color: fill }, objectName: `badge ${n}` });
  slide.addText(String(n), { x, y, w: 0.42, h: 0.42, fontSize: 15, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true });
}

const chartText = { catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", legendFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt", titleFontFace: "+mn-lt" };
const axisStyle = { catAxisLabelColor: "475569", valAxisLabelColor: "475569", catAxisLabelFontSize: 12, valAxisLabelFontSize: 11, valGridLine: { color: "E2E8F0", size: 0.75 }, catGridLine: { style: "none" }, catAxisLineShow: false, valAxisLineShow: false };

// ---------------------------------------------------------------- 1. title
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "DARK", sectionTitle: "Introduction" });
s.addText("Validating the Asset Allocation Engine", { placeholder: "title" });
s.addText("How we check the allocation is right when there is no single “correct” answer to compare against", { placeholder: "body" });
s.addNotes("This deck explains how we evaluate the asset allocation page. Accuracy, as used for the risk-tier model, does not apply here, so we validate the engine against five properties instead.");

// ---------------------------------------------------------------- 2. why not accuracy
s = contentSlide("No “true” allocation exists, so we validate it", "Introduction");
s.addText([
  { text: "The risk-tier model can be scored against a known tier for each person.", options: { bullet: true, breakLine: true } },
  { text: "An allocation has no labelled right answer, so “accuracy” does not apply.", options: { bullet: true, breakLine: true } },
  { text: "Instead we test whether it is correct, optimal, sensible, safe in real markets and stable.", options: { bullet: true } },
], { x: 0.5, y: 1.3, w: 4.2, h: 3.4, fontSize: 16, color: C.text1, paraSpaceAfter: 12, valign: "top", margin: 0, isTextBox: true });

const flow = [
  ["Final risk tier", "from the risk profile (1–5)", C.text2],
  ["Layer 1 · tier limits", "min–max % for each asset class", C.accent3],
  ["Layer 2 · optimizer", "best risk-adjusted return (Sharpe) inside the limits", C.accent1],
  ["Target split", "cash · debt · equity · real assets · alternatives", C.text1],
];
flow.forEach(([head, sub, col], i) => {
  const y = 1.25 + i * 0.95;
  card(s, 5.2, y, 4.3, 0.72, `flow step ${i + 1}`);
  s.addShape(pres.shapes.OVAL, { x: 5.35, y: y + 0.16, w: 0.4, h: 0.4, fill: { color: col }, line: { color: col }, objectName: `flow dot ${i + 1}` });
  s.addText(head, { x: 5.9, y: y + 0.06, w: 3.5, h: 0.32, fontSize: 15, bold: true, color: C.text1, margin: 0, isTextBox: true });
  s.addText(sub, { x: 5.9, y: y + 0.37, w: 3.5, h: 0.28, fontSize: 12, color: C.text2, margin: 0, isTextBox: true });
  if (i < flow.length - 1) s.addShape(pres.shapes.DOWN_ARROW, { x: 7.2, y: y + 0.74, w: 0.3, h: 0.19, fill: { color: "94A3B8" }, line: { color: "94A3B8" }, objectName: `flow arrow ${i + 1}` });
});
s.addNotes("The allocation engine has two layers. Layer 1 is a fixed table of minimum and maximum percentages for each asset class, per tier. Layer 2 is an optimizer that picks the split with the best Sharpe ratio inside those limits.");

// ---------------------------------------------------------------- 3. five checks
pres.addSection({ title: "Validation" });
s = contentSlide("Five checks replace a single accuracy score", "Validation");
const checks = [
  ["Correctness", "Does it obey its own rules?", "Done"],
  ["Optimality", "Is it the best split inside the limits?", "Done"],
  ["Sensibility", "Is it close to expert and industry portfolios?", "Planned"],
  ["Backtest", "Does it behave as promised on real market data?", "Planned"],
  ["Robustness", "Does a small change in assumptions flip it?", "Planned"],
];
checks.forEach(([head, q, status], i) => {
  const x = 0.5 + i * 1.84, w = 1.66;
  card(s, x, 1.35, w, 3.3, `check card ${i + 1}`);
  const done = status === "Done";
  numberBadge(s, x + 0.2, 1.55, i + 1, done ? C.accent1 : C.accent2);
  s.addText(head, { x: x + 0.2, y: 2.15, w: w - 0.35, h: 0.4, fontSize: 16, bold: true, color: C.text1, margin: 0, isTextBox: true });
  s.addText(q, { x: x + 0.2, y: 2.6, w: w - 0.35, h: 1.3, fontSize: 14, color: C.text2, valign: "top", margin: 0, isTextBox: true });
  s.addText(done ? "✓ Done" : "Planned", { x: x + 0.2, y: 4.1, w: w - 0.35, h: 0.35, fontSize: 13, bold: true, color: done ? C.accent1 : C.accent2, margin: 0, isTextBox: true });
});
s.addNotes("Checks 1 and 2 have been run on the code. Checks 3 to 5 need external data: benchmark portfolios, expert ratings and historical index data.");

// ---------------------------------------------------------------- 4. correctness
s = contentSlide("Check 1 · Correctness: every rule holds", "Validation");
const rules = [
  ["Weights add up to 100%", "every tier"],
  ["Every weight stays within its tier’s limits", "every tier and asset class"],
  ["Optimizer converges, never falls back to the midpoint", "every tier"],
  ["The same tier always gives the same split", "repeat runs"],
];
rules.forEach(([head, scope], i) => {
  const x = 0.5 + (i % 2) * 4.6, y = 1.3 + Math.floor(i / 2) * 1.75;
  card(s, x, y, 4.4, 1.5, `rule card ${i + 1}`);
  s.addText("100%", { x: x + 0.3, y: y + 0.2, w: 1.6, h: 1.1, fontFace: THEME.headFontFace, fontSize: 36, bold: true, color: C.accent1, valign: "middle", margin: 0, isTextBox: true });
  s.addText(head, { x: x + 2.0, y: y + 0.25, w: 2.25, h: 0.75, fontSize: 15, bold: true, color: C.text1, valign: "top", margin: 0, isTextBox: true });
  s.addText(`pass rate · ${scope}`, { x: x + 2.0, y: y + 1.0, w: 2.25, h: 0.35, fontSize: 12, color: C.text2, margin: 0, isTextBox: true });
});
s.addNotes("These are pass/fail checks on the engine's own guarantees. All 5 tiers pass all 4 checks.");

// ---------------------------------------------------------------- 5. optimality
s = contentSlide("Check 2 · Optimality: beats 20,000 random splits", "Validation");
card(s, 0.5, 1.3, 3.2, 3.5, "optimality stat card");
s.addText("100%", { x: 0.75, y: 1.5, w: 2.8, h: 1.0, fontFace: THEME.headFontFace, fontSize: 54, bold: true, color: C.accent1, margin: 0, isTextBox: true });
s.addText("of 20,000 random valid portfolios beaten on Sharpe ratio, in every tier", { x: 0.75, y: 2.55, w: 2.75, h: 1.0, fontSize: 15, color: C.text1, valign: "top", margin: 0, isTextBox: true });
s.addText(`Sharpe ratio by tier: ${SHARPE.map((v) => v.toFixed(2)).join(" · ")}`, { x: 0.75, y: 3.75, w: 2.75, h: 0.8, fontSize: 12, color: C.text2, valign: "top", margin: 0, isTextBox: true });
s.addChart(pres.charts.BAR, [
  { name: "Expected return (%)", labels: TIERS, values: RET },
  { name: "Volatility (%)", labels: TIERS, values: VOL },
], {
  x: 4.0, y: 1.2, w: 5.5, h: 3.7, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60,
  chartColors: [HEX.accent1, HEX.accent2], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 11, dataLabelColor: "1B2A41", dataLabelFormatCode: "0.0",
  showLegend: true, legendPos: "t", legendFontSize: 12, legendColor: "475569",
  showTitle: true, title: "Return and risk rise steadily with tier", titleFontSize: 14, titleColor: "1B2A41",
  valAxisMinVal: 0, valAxisMaxVal: 14, valAxisMajorUnit: 2, valAxisLabelFormatCode: "0", ...axisStyle, ...chartText,
});
s.addNotes("Within each tier's limits, the optimizer's split scored a higher Sharpe ratio than all 20,000 randomly drawn valid splits. Expected return rises from 7.1% to 10.3% and volatility from 4.4% to 13.0% as the tier goes up, which is the behaviour we want.");

// ---------------------------------------------------------------- 6. split by tier
s = contentSlide("The split shifts from safety to growth as tier rises", "Validation");
s.addChart(pres.charts.BAR, Object.entries(SPLIT).map(([name, values]) => ({ name, labels: TIERS, values })), {
  x: 0.5, y: 1.2, w: 6.0, h: 3.9, barDir: "col", barGrouping: "percentStacked", barGapWidthPct: 45,
  chartColors: ASSET_COLORS, showValue: true, dataLabelPosition: "ctr", dataLabelFontSize: 10, dataLabelColor: "FFFFFF", dataLabelFormatCode: '[<4]"";0',
  showLegend: true, legendPos: "b", legendFontSize: 12, legendColor: "475569",
  valAxisLabelFormatCode: "0%", ...axisStyle, ...chartText,
});
const facts = [["15% → 56%", "equity, tier 1 to tier 5"], ["30% → 2%", "cash, tier 1 to tier 5"], ["100%", "of each split stays within its tier’s limits"]];
facts.forEach(([big, small], i) => {
  const y = 1.3 + i * 1.25;
  card(s, 6.8, y, 2.7, 1.05, `split fact ${i + 1}`);
  s.addText(big, { x: 7.0, y: y + 0.1, w: 2.4, h: 0.5, fontFace: THEME.headFontFace, fontSize: 24, bold: true, color: C.text1, margin: 0, isTextBox: true });
  s.addText(small, { x: 7.0, y: y + 0.6, w: 2.4, h: 0.35, fontSize: 12, color: C.text2, margin: 0, isTextBox: true });
});
s.addNotes("Target split per tier as produced by the engine. Cash and debt dominate at tier 1; equity becomes the largest holding by tier 4.");

// ---------------------------------------------------------------- 7. watch-out
s = contentSlide("Watch-out: the limits table drives the split", "Validation");
card(s, 0.5, 1.3, 3.0, 3.5, "watch-out stat card", "FEF3C7");
s.addText("4 of 5", { x: 0.75, y: 1.5, w: 2.6, h: 1.0, fontFace: THEME.headFontFace, fontSize: 48, bold: true, color: C.accent2, margin: 0, isTextBox: true });
s.addText("weights sit exactly on a limit, in every tier", { x: 0.75, y: 2.55, w: 2.55, h: 0.8, fontSize: 15, color: C.text1, valign: "top", margin: 0, isTextBox: true });
s.addText("So the optimizer only fine-tunes; the hand-set limits must be validated themselves (checks 3–4).", { x: 0.75, y: 3.45, w: 2.55, h: 1.2, fontSize: 13, color: C.text2, valign: "top", margin: 0, isTextBox: true });
const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.dk1 }, align: "center" } });
const rows = [[hdr("Tier"), hdr("Equity limits"), hdr("Equity chosen"), hdr("Where it lands")]];
const lands = ["at maximum", "at maximum", "near minimum", "near minimum", "near minimum"];
TIERS.forEach((t, i) => rows.push([
  { text: t, options: { align: "center" } },
  { text: `${EQ_RANGE[i]}%`, options: { align: "center" } },
  { text: `${SPLIT.Equity[i]}%`, options: { align: "center", bold: true } },
  { text: lands[i], options: { align: "center", color: lands[i] === "at maximum" ? HEX.accent3 : HEX.accent2 } },
]));
s.addTable(rows, { x: 3.9, y: 1.4, w: 5.6, colW: [1.0, 1.5, 1.5, 1.6], rowH: 0.5, fontSize: 14, color: HEX.dk1, fontFace: THEME.bodyFontFace, valign: "middle", border: { type: "solid", pt: 0.75, color: "E2E8F0" }, fill: { color: "FFFFFF" } });
s.addNotes("Because the optimizer pushes most weights to a limit, the limits table effectively sets the allocation. Equity goes to its maximum in tiers 1 and 2 and stays near its minimum in tiers 3 to 5. This is why benchmarking and backtesting the limits matter most.");

// ---------------------------------------------------------------- 8. planned checks
pres.addSection({ title: "Next steps" });
s = contentSlide("Checks 3–5 test the limits against the real world", "Next steps");
const plans = [
  ["3", "Sensibility", ["Distance from benchmark portfolios (sum of % differences)", "Equity gap vs benchmark", "Expert agreement % or Cohen’s κ"]],
  ["4", "Backtest", ["Return (CAGR), volatility, Sharpe per tier", "Maximum drawdown: tier 1 ≪ tier 5", "Stress tests: 2008, 2020 crash", "Tier vs realised risk (Spearman ≈ 1)"]],
  ["5", "Robustness", ["Shift each return / volatility assumption by ±1 pp", "Measure how much the split moves (turnover)", "Small change = stable advice"]],
];
plans.forEach(([n, head, items], i) => {
  const x = 0.5 + i * 3.07, w = 2.87;
  card(s, x, 1.3, w, 3.5, `plan card ${n}`);
  numberBadge(s, x + 0.25, 1.5, n, C.accent2);
  s.addText(head, { x: x + 0.8, y: 1.5, w: w - 1.0, h: 0.42, fontSize: 17, bold: true, color: C.text1, valign: "middle", margin: 0, isTextBox: true });
  s.addText(items.map((t, k) => ({ text: t, options: { bullet: true, breakLine: k < items.length - 1 } })),
    { x: x + 0.25, y: 2.15, w: w - 0.45, h: 2.5, fontSize: 14, color: C.text2, paraSpaceAfter: 8, valign: "top", margin: 0, isTextBox: true });
});
s.addNotes("Sensibility compares each tier with published model portfolios and asks finance experts to rate them. The backtest uses historical Indian index data as proxies: a liquid fund for cash, a CRISIL bond index for debt, Nifty 50 for equity, gold or REITs for real assets. Robustness checks how sensitive the split is to the assumed returns and volatilities.");

// ---------------------------------------------------------------- 9. summary
s = pres.addSlide({ masterName: "DARK", sectionTitle: "Next steps" });
s.addText("Validated, not “accurate”", { placeholder: "title" });
s.addText("The engine passes 100% of its rule checks, beats 20,000 random valid portfolios on risk-adjusted return, and its risk and return rise steadily with tier. Next: benchmark and backtest the tier limits.", { placeholder: "body" });
s.addNotes("Summary line for the presentation. Add backtest and benchmark numbers here once checks 3 to 5 are complete.");

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("saved " + OUT);
})();
