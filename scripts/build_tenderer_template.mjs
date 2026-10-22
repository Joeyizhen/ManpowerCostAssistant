import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = fileURLToPath(new URL("../outputs/", import.meta.url));
const outputPath = `${outputDir}Tenderer_Manpower_Submission_Template.xlsx`;
const workbook = Workbook.create();
const navy = "#173B63";
const teal = "#147D74";
const lightBlue = "#EAF2F8";
const inputYellow = "#FFF2CC";
const lightGrey = "#F3F5F7";
const red = "#FDE8E8";
const font = "Arial";

const instructions = workbook.worksheets.add("Instructions");
const details = workbook.worksheets.add("Submission Details");
const summary = workbook.worksheets.add("Cost Summary");
const years = Array.from({ length: 6 }, (_, index) => workbook.worksheets.add(`Year ${index + 1}`));
const assumptions = workbook.worksheets.add("Assumptions & Exclusions");
const lists = workbook.worksheets.add("Lists");

for (const sheet of [instructions, details, summary, ...years, assumptions, lists]) {
  sheet.showGridLines = false;
}
instructions.tabColor = navy;
summary.tabColor = teal;
details.tabColor = "#5B9BD5";
assumptions.tabColor = "#A5A5A5";

instructions.getRange("A2:H2").merge();
instructions.getRange("A2").values = [["Tenderer Manpower Cost Submission Template"]];
instructions.getRange("A2").format = { font: { name: font, size: 16, bold: true, color: navy } };
instructions.getRange("A4:H4").merge();
instructions.getRange("A4").values = [["Use this workbook for manpower pricing submitted through the FM Manpower Cost Assistant."]];
instructions.getRange("A6:B14").values = [
  ["Step", "What to do"],
  [1, "Complete Submission Details, including the tender reference, tenderer name and contract period."],
  [2, "Complete each applicable Year tab. Use one row for each priced manpower role."],
  [3, "Enter monthly inclusive rates in SGD. Do not enter annual, daily or hourly rates."],
  [4, "Use headcount or FTE consistently for the same role across all years."],
  [5, "State duties, shift pattern and inclusions so reviewers can compare like with like."],
  [6, "Record pricing assumptions and excluded items in Assumptions & Exclusions."],
  [7, "Check the Cost Summary. Every annual total should agree with the submitted pricing schedule."],
  [8, "Submit this completed .xlsx file without renaming or deleting the Year tabs."],
];
instructions.getRange("A6:B6").format = { fill: navy, font: { name: font, bold: true, color: "#FFFFFF" } };
instructions.getRange("A16:B22").values = [
  ["Required field", "Accepted entry"],
  ["Role", "Tenderer's role title, e.g. Facilities Manager, M&E Engineer, Technician"],
  ["Contract Year", "Already fixed on each Year tab"],
  ["Quantity", "Number of headcount or FTE, including permitted decimals for FTE"],
  ["Quantity Unit", "headcount or fte"],
  ["Monthly Rate (SGD)", "Inclusive monthly rate per head or FTE in Singapore dollars"],
  ["Source", "Tenderer reference such as pricing schedule section or internal line reference"],
];
instructions.getRange("A16:B16").format = { fill: teal, font: { name: font, bold: true, color: "#FFFFFF" } };
instructions.getRange("A6:B22").format.font = { name: font, size: 10 };
instructions.getRange("A6:B22").format.wrapText = true;
instructions.getRange("A:A").format.columnWidth = 18;
instructions.getRange("B:B").format.columnWidth = 78;
instructions.freezePanes.freezeRows(5);

details.getRange("A2:D2").merge();
details.getRange("A2").values = [["Submission Details"]];
details.getRange("A2").format = { font: { name: font, size: 16, bold: true, color: navy } };
details.getRange("A4:B15").values = [
  ["Field", "Tenderer entry"],
  ["Tender reference", ""],
  ["Tenderer legal name", ""],
  ["UEN / registration number", ""],
  ["Submission revision", 1],
  ["Contact person", ""],
  ["Contact email", ""],
  ["Contract start date", ""],
  ["Base contract years", 6],
  ["Option years", 0],
  ["Currency", "SGD"],
  ["Pricing frequency", "Monthly"],
];
details.getRange("A4:B4").format = { fill: navy, font: { name: font, bold: true, color: "#FFFFFF" } };
details.getRange("B5:B15").format.fill = inputYellow;
details.getRange("A4:B15").format.font = { name: font, size: 10 };
details.getRange("A:A").format.columnWidth = 34;
details.getRange("B:B").format.columnWidth = 48;
details.getRange("B11").format.numberFormat = "dd-mmm-yyyy";
details.getRange("B12:B13").dataValidation = { rule: { type: "whole", operator: "between", formula1: 0, formula2: 20 } };

const headers = [
  "Role", "Contract Year", "Quantity", "Quantity Unit", "Monthly Rate (SGD)", "Currency",
  "Pricing Frequency", "Annual Cost (SGD)", "Cost Component", "Shift Pattern", "Hours per Week",
  "Duties / Responsibilities", "Source", "Notes / Inclusions",
];
for (let index = 0; index < years.length; index += 1) {
  const sheet = years[index];
  const year = index + 1;
  sheet.getRange("A2:N2").merge();
  sheet.getRange("A2").values = [[`Contract Year ${year} Manpower Schedule`]];
  sheet.getRange("A2").format = { font: { name: font, size: 15, bold: true, color: navy } };
  sheet.getRange("A3:N3").merge();
  sheet.getRange("A3").values = [["Yellow cells are for tenderer input. Add one row per manpower role and leave unused rows blank."]];
  sheet.getRange("A3").format = { font: { name: font, italic: true, color: "#52606D" } };
  sheet.getRange("A5:N5").values = [headers];
  sheet.getRange("A5:N5").format = {
    fill: teal, font: { name: font, bold: true, color: "#FFFFFF" },
    wrapText: true, horizontalAlignment: "center", verticalAlignment: "center",
  };
  const rows = 40;
  sheet.getRange(`A6:N${5 + rows}`).format.font = { name: font, size: 10 };
  sheet.getRange(`A6:G${5 + rows}`).format.fill = inputYellow;
  sheet.getRange(`I6:N${5 + rows}`).format.fill = inputYellow;
  sheet.getRange(`B6:B${5 + rows}`).values = Array.from({ length: rows }, () => [year]);
  sheet.getRange(`F6:F${5 + rows}`).values = Array.from({ length: rows }, () => ["SGD"]);
  sheet.getRange(`G6:G${5 + rows}`).values = Array.from({ length: rows }, () => ["Monthly"]);
  sheet.getRange("H6").formulas = [["=IF(OR(A6=\"\",C6=\"\",E6=\"\"),\"\",C6*E6*12)"]];
  sheet.getRange(`H6:H${5 + rows}`).fillDown();
  sheet.getRange(`H6:H${5 + rows}`).format.fill = lightBlue;
  sheet.getRange(`C6:C${5 + rows}`).dataValidation = { rule: { type: "decimal", operator: "between", formula1: 0, formula2: 10000 } };
  sheet.getRange(`D6:D${5 + rows}`).dataValidation = { rule: { type: "list", values: ["headcount", "fte"] } };
  sheet.getRange(`E6:E${5 + rows}`).dataValidation = { rule: { type: "decimal", operator: "between", formula1: 0, formula2: 1000000 } };
  sheet.getRange(`I6:I${5 + rows}`).dataValidation = { rule: { type: "list", formula1: "Lists!$A$2:$A$13" } };
  sheet.getRange(`C6:C${5 + rows}`).format.numberFormat = "#,##0.00";
  sheet.getRange(`E6:E${5 + rows}`).format.numberFormat = '"S$" #,##0.00';
  sheet.getRange(`H6:H${5 + rows}`).format.numberFormat = '"S$" #,##0.00';
  sheet.getRange(`K6:K${5 + rows}`).format.numberFormat = "0.0";
  sheet.getRange(`A5:N${5 + rows}`).format.borders = { preset: "all", style: "thin", color: "#D9E1E8" };
  sheet.getRange("A:A").format.columnWidth = 26;
  sheet.getRange("B:B").format.columnWidth = 13;
  sheet.getRange("C:D").format.columnWidth = 14;
  sheet.getRange("E:H").format.columnWidth = 20;
  sheet.getRange("I:I").format.columnWidth = 30;
  sheet.getRange("J:K").format.columnWidth = 16;
  sheet.getRange("L:L").format.columnWidth = 46;
  sheet.getRange("M:M").format.columnWidth = 28;
  sheet.getRange("N:N").format.columnWidth = 38;
  sheet.getRange(`L6:N${5 + rows}`).format.wrapText = true;
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(2);
}

summary.getRange("A2:H2").merge();
summary.getRange("A2").values = [["Manpower Cost Summary"]];
summary.getRange("A2").format = { font: { name: font, size: 16, bold: true, color: navy } };
summary.getRange("A5:C12").values = [
  ["Contract period", "Annual manpower cost (SGD)", "Status"],
  ["Year 1", null, null], ["Year 2", null, null], ["Year 3", null, null],
  ["Year 4", null, null], ["Year 5", null, null], ["Year 6", null, null],
  ["Full contract", null, null],
];
summary.getRange("A5:C5").format = { fill: navy, font: { name: font, bold: true, color: "#FFFFFF" } };
for (let index = 0; index < 6; index += 1) {
  const row = 6 + index;
  summary.getRange(`B${row}`).formulas = [[`=SUM('Year ${index + 1}'!H6:H45)`]];
  summary.getRange(`C${row}`).formulas = [[`=IF(COUNTA('Year ${index + 1}'!A6:A45)=0,"Not completed","Check completed rows")`]];
}
summary.getRange("B12").formulas = [["=SUM(B6:B11)"]];
summary.getRange("C12").formulas = [["=IF(COUNTIF(C6:C11,\"Not completed\")>0,\"Incomplete\",\"Review totals\")"]];
summary.getRange("B6:B12").format.numberFormat = '"S$" #,##0.00';
summary.getRange("A12:C12").format.font = { name: font, bold: true };
summary.getRange("A5:C12").format.borders = { preset: "all", style: "thin", color: "#D9E1E8" };
summary.getRange("A:A").format.columnWidth = 24;
summary.getRange("B:B").format.columnWidth = 28;
summary.getRange("C:C").format.columnWidth = 24;

assumptions.getRange("A2:E2").merge();
assumptions.getRange("A2").values = [["Pricing Assumptions and Exclusions"]];
assumptions.getRange("A2").format = { font: { name: font, size: 16, bold: true, color: navy } };
assumptions.getRange("A5:E5").values = [["S/N", "Type", "Applies to Role / Cost Component", "Tenderer Statement", "Source Reference"]];
assumptions.getRange("A5:E5").format = { fill: teal, font: { name: font, bold: true, color: "#FFFFFF" }, wrapText: true };
assumptions.getRange("A6:A35").values = Array.from({ length: 30 }, (_, i) => [i + 1]);
assumptions.getRange("B6:E35").format.fill = inputYellow;
assumptions.getRange("B6:B35").dataValidation = { rule: { type: "list", values: ["Assumption", "Inclusion", "Exclusion", "Qualification"] } };
assumptions.getRange("A5:E35").format.borders = { preset: "all", style: "thin", color: "#D9E1E8" };
assumptions.getRange("A:A").format.columnWidth = 8;
assumptions.getRange("B:B").format.columnWidth = 18;
assumptions.getRange("C:C").format.columnWidth = 36;
assumptions.getRange("D:D").format.columnWidth = 64;
assumptions.getRange("E:E").format.columnWidth = 32;
assumptions.getRange("C6:E35").format.wrapText = true;
assumptions.freezePanes.freezeRows(5);

lists.getRange("A1").values = [["Cost Components"]];
lists.getRange("A2:A13").values = [
  ["Manpower Cost"], ["Cleaning & Waste Management"], ["Estate Management"],
  ["Landscape Maintenance"], ["Mechanical & Electrical Services"], ["Security Services"],
  ["Reception"], ["Helpdesk Management"], ["Office Management Functions"],
  ["Data Centre Maintenance"], ["Building Maintenance Works"], ["Other Services"],
];
lists.getRange("A1:A13").format.font = { name: font, size: 10 };
lists.getRange("A1").format = { fill: lightGrey, font: { name: font, bold: true, color: navy } };
lists.getRange("A:A").format.columnWidth = 48;

workbook.recalculate();
const inspect = await workbook.inspect({
  kind: "table", range: "Cost Summary!A2:C12", include: "values,formulas", tableMaxRows: 15, tableMaxCols: 5,
});
console.log(inspect.ndjson);
const errors = await workbook.inspect({
  kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan",
});
console.log(errors.ndjson);
await fs.mkdir(outputDir, { recursive: true });
for (const sheet of [instructions, details, summary, ...years, assumptions]) {
  const preview = await workbook.render({ sheetName: sheet.name, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${outputDir}preview_${sheet.name.replaceAll(" ", "_")}.png`, new Uint8Array(await preview.arrayBuffer()));
}
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
