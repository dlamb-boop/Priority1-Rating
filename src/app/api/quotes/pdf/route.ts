import { assertCustomerSafe, buildCustomerQuote, customerQuoteFilename } from "@/lib/customer-quote";
import { renderCustomerPdf } from "@/lib/pdf";
import type { PdfRequest } from "@/lib/customer-quote";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  let body: PdfRequest;
  try {
    body = (await request.json()) as PdfRequest;
  } catch {
    return Response.json({ error: "Send a JSON quote." }, { status: 400 });
  }

  try {
    const document = buildCustomerQuote(body);
    assertCustomerSafe(document);
    const bytes = await renderCustomerPdf(document);
    const filename = customerQuoteFilename(document);
    return new Response(new Uint8Array(bytes), {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="${filename}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "The PDF could not be created.";
    return Response.json({ error: message }, { status: 400 });
  }
}
