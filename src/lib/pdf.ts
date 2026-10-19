import PDFDocument from "pdfkit";
import { preparedByLine } from "@/lib/customer-quote";
import type { CustomerQuoteDocument } from "@/lib/types";
import { formatDimensions, formatLongDate, formatMoney, formatTransitDays, formatWeight } from "@/lib/format";

const PINE = "#0f6e56";
const PINE_DEEP = "#0c3d32";
const INK = "#14241c";
const MUTED = "#5c6b63";
const LINE = "#e2d9c9";
const PAPER = "#f7f4ee";
const WHITE = "#ffffff";

function money(amount: number, currency: string): string {
  try {
    return formatMoney(amount, currency || "USD");
  } catch {
    return formatMoney(amount);
  }
}

export function renderCustomerPdf(document: CustomerQuoteDocument): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const pdf = new PDFDocument({
      size: "LETTER",
      margin: 0,
      bufferPages: true,
      info: {
        Title: "EasyPost Freight Quote",
        Author: "Dawson Lamb, EasyPost",
        Subject: "Customer freight quote",
        Keywords: "EasyPost, freight quote",
        Creator: "EasyPost Freight Quotes",
        Producer: "EasyPost",
      },
    });
    const chunks: Buffer[] = [];
    pdf.on("data", (chunk: Buffer) => chunks.push(chunk));
    pdf.on("end", () => resolve(Buffer.concat(chunks)));
    pdf.on("error", reject);

    drawDocument(pdf, document);
    const range = pdf.bufferedPageRange();
    for (let pageIndex = range.start; pageIndex < range.start + range.count; pageIndex += 1) {
      pdf.switchToPage(pageIndex);
      drawFooter(pdf, document);
    }
    pdf.end();
  });
}

function drawDocument(pdf: PDFKit.PDFDocument, document: CustomerQuoteDocument): void {
  const pageWidth = pdf.page.width;
  let y = drawHeader(pdf, document, pageWidth);

  y = drawParties(pdf, document, y);
  y = drawShipment(pdf, document, y);
  y = sectionTitle(pdf, "Carrier options", y + 8);

  document.options.forEach((option, index) => {
    const blockHeight = 96 + option.charges.length * 16;
    if (y + blockHeight > pdf.page.height - 86) {
      pdf.addPage();
      y = drawHeader(pdf, document, pageWidth, true);
    }
    y = drawOption(pdf, option, index, y);
  });
}

function drawHeader(
  pdf: PDFKit.PDFDocument,
  document: CustomerQuoteDocument,
  pageWidth: number,
  continued = false,
): number {
  pdf.rect(0, 0, pageWidth, continued ? 58 : 92).fill(PINE_DEEP);
  pdf.fillColor(WHITE).font("Helvetica").fontSize(10).text("EASYPOST", 48, continued ? 16 : 22, {
    characterSpacing: 1.6,
  });
  pdf.font("Helvetica-Bold").fontSize(continued ? 16 : 24).text(continued ? "Freight quote" : "Freight quote", 48, continued ? 30 : 40);

  pdf.font("Helvetica").fontSize(9).fillColor("#d7efe6");
  const right = pageWidth - 220;
  pdf.text(document.reference, right, continued ? 16 : 28, { width: 172, align: "right" });
  pdf.text(formatLongDate(document.quoteDate), right, continued ? 30 : 42, { width: 172, align: "right" });
  if (!continued) {
    pdf.text(`Valid through ${formatLongDate(document.validThrough)}`, right, 56, {
      width: 172,
      align: "right",
    });
  }
  return continued ? 78 : 114;
}

function drawParties(pdf: PDFKit.PDFDocument, document: CustomerQuoteDocument, y: number): number {
  const preparedFor = [document.customerName, document.company].filter(Boolean);
  pdf.fillColor(MUTED).font("Helvetica").fontSize(9).text("PREPARED FOR", 48, y, { characterSpacing: 0.8 });
  pdf.fillColor(INK).font("Helvetica-Bold").fontSize(14);
  if (preparedFor.length === 0) {
    pdf.text("Prospective customer", 48, y + 14);
  } else {
    pdf.text(preparedFor[0], 48, y + 14);
    if (preparedFor[1]) {
      pdf.font("Helvetica").fontSize(11).fillColor(INK).text(preparedFor[1], 48, y + 34);
    }
  }
  return y + (preparedFor.length > 1 ? 62 : 48);
}

function drawShipment(pdf: PDFKit.PDFDocument, document: CustomerQuoteDocument, y: number): number {
  y = sectionTitle(pdf, "Shipment", y);
  const boxTop = y;
  pdf.roundedRect(48, boxTop, 516, 78, 8).fill(PAPER);
  pdf.fillColor(MUTED).font("Helvetica").fontSize(8).text("ORIGIN", 64, boxTop + 12);
  pdf.fillColor(INK).font("Helvetica-Bold").fontSize(12).text(document.shipment.originLabel, 64, boxTop + 26, {
    width: 210,
  });
  pdf.fillColor(MUTED).font("Helvetica").fontSize(8).text("DESTINATION", 300, boxTop + 12);
  pdf.fillColor(INK).font("Helvetica-Bold").fontSize(12).text(document.shipment.destinationLabel, 300, boxTop + 26, {
    width: 240,
  });
  const facts = [
    `Pickup ${formatLongDate(document.shipment.pickupDate)}`,
    document.shipment.totalWeight != null ? formatWeight(document.shipment.totalWeight) : null,
    document.shipment.distanceMiles != null ? `${document.shipment.distanceMiles.toLocaleString("en-US")} miles` : null,
  ]
    .filter(Boolean)
    .join("   ·   ");
  pdf.fillColor(MUTED).font("Helvetica").fontSize(9).text(facts, 64, boxTop + 52, { width: 480 });
  y = boxTop + 94;

  if (document.shipment.items.length > 0) {
    const columns = [48, 110, 200, 270, 340, 430];
    pdf.rect(48, y, 516, 18).fill("#e7f3ee");
    pdf.fillColor(PINE_DEEP).font("Helvetica-Bold").fontSize(8);
    ["Class", "Packaging", "Units", "Weight", "Dimensions", "Notes"].forEach((label, index) => {
      pdf.text(label, columns[index], y + 5, { width: 90 });
    });
    y += 18;
    document.shipment.items.forEach((item, index) => {
      const rowTop = y;
      if (index % 2 === 0) pdf.rect(48, rowTop, 516, 22).fill("#fffdf8");
      const notes = [
        item.description,
        item.isHazardous ? "Hazmat" : null,
        item.isStackable ? "Stackable" : null,
      ]
        .filter(Boolean)
        .join(", ");
      pdf.fillColor(INK).font("Helvetica").fontSize(9);
      const cells = [
        item.freightClass,
        item.packagingType,
        String(item.units),
        formatWeight(item.totalWeight),
        item.length && item.width && item.height ? formatDimensions(item.length, item.width, item.height) : "—",
        notes || "—",
      ];
      cells.forEach((cell, cellIndex) => {
        pdf.text(cell, columns[cellIndex], rowTop + 6, { width: cellIndex === 5 ? 120 : 88, lineBreak: false });
      });
      y += 22;
    });
    pdf.moveTo(48, y).lineTo(564, y).strokeColor(LINE).lineWidth(1).stroke();
    y += 12;
  }

  if (document.shipment.accessorials.length > 0) {
    pdf.fillColor(MUTED).font("Helvetica").fontSize(9).text("Accessorials", 48, y);
    pdf.fillColor(INK).font("Helvetica").fontSize(10).text(document.shipment.accessorials.join("  ·  "), 48, y + 14, {
      width: 516,
    });
    y += 36;
  }
  return y;
}

function sectionTitle(pdf: PDFKit.PDFDocument, title: string, y: number): number {
  pdf.fillColor(PINE).font("Helvetica-Bold").fontSize(12).text(title, 48, y);
  return y + 20;
}

function drawOption(
  pdf: PDFKit.PDFDocument,
  option: CustomerQuoteDocument["options"][number],
  index: number,
  y: number,
): number {
  const chargeHeight = option.charges.length * 16;
  const height = 64 + chargeHeight + (option.charges.length ? 12 : 0);
  pdf.roundedRect(48, y, 516, height, 8).lineWidth(1).strokeColor(LINE).stroke();
  pdf.fillColor(MUTED).font("Helvetica").fontSize(8).text(`OPTION ${index + 1}`, 64, y + 12, { characterSpacing: 0.6 });
  pdf.fillColor(INK).font("Helvetica-Bold").fontSize(13).text(option.carrierName, 64, y + 26, { width: 320 });
  const meta = [
    option.scac || null,
    option.serviceLevel,
    option.laneType ? option.laneType.toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase()) : null,
  ]
    .filter(Boolean)
    .join("  ·  ");
  pdf.fillColor(MUTED).font("Helvetica").fontSize(9).text(meta, 64, y + 46, { width: 330 });

  pdf.fillColor(PINE_DEEP).font("Helvetica-Bold").fontSize(16).text(money(option.price, option.currency), 380, y + 24, {
    width: 164,
    align: "right",
  });

  const timing = [
    formatTransitDays(option.transitDays),
    option.deliveryDate ? `Delivers ${formatLongDate(option.deliveryDate)}` : null,
    option.expirationDate ? `Expires ${formatLongDate(option.expirationDate)}` : null,
  ]
    .filter(Boolean)
    .join("   ·   ");
  let cursor = y + 64;
  if (option.charges.length === 0) {
    pdf.fillColor(MUTED).font("Helvetica").fontSize(9).text(timing, 64, y + 64, { width: 470 });
    return y + height + 10;
  }

  option.charges.forEach((charge) => {
    pdf.fillColor(INK).font("Helvetica").fontSize(9).text(charge.description, 64, cursor, { width: 360 });
    pdf.text(money(charge.amount, option.currency), 430, cursor, { width: 114, align: "right" });
    cursor += 16;
  });
  pdf.fillColor(MUTED).font("Helvetica").fontSize(8).text(timing, 64, cursor + 2, { width: 470 });
  return y + height + 10;
}

function drawFooter(pdf: PDFKit.PDFDocument, document: CustomerQuoteDocument): void {
  const bottom = pdf.page.height - 58;
  pdf.moveTo(48, bottom).lineTo(564, bottom).strokeColor(LINE).lineWidth(1).stroke();
  pdf.fillColor(INK).font("Helvetica").fontSize(8).text(preparedByLine(), 48, bottom + 10, { width: 516 });
  const note = document.mentionCapacityPartner
    ? "Estimate only. This is not a tender. The rate can change if the shipment differs from the details above. Capacity sourced through Priority1."
    : "Estimate only. This is not a tender. The rate can change if the shipment differs from the details above.";
  pdf.fillColor(MUTED).font("Helvetica").fontSize(8).text(note, 48, bottom + 24, { width: 516 });
}
