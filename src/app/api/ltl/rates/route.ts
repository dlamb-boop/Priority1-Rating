import { errorPayload, quoteLtl } from "@/lib/quote-service";
import type { LtlQuoteInput } from "@/lib/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  let body: LtlQuoteInput;
  try {
    body = (await request.json()) as LtlQuoteInput;
  } catch {
    return Response.json({ error: "Send a JSON quote request." }, { status: 400 });
  }
  try {
    const quote = await quoteLtl(body);
    return Response.json(quote);
  } catch (error) {
    const payload = errorPayload(error);
    return Response.json(payload.body, { status: payload.status });
  }
}
