import { errorPayload, quoteTl } from "@/lib/quote-service";
import type { TlQuoteInput } from "@/lib/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  let body: TlQuoteInput;
  try {
    body = (await request.json()) as TlQuoteInput;
  } catch {
    return Response.json({ error: "Send a JSON quote request." }, { status: 400 });
  }
  try {
    const quote = await quoteTl(body);
    return Response.json(quote);
  } catch (error) {
    const payload = errorPayload(error);
    return Response.json(payload.body, { status: payload.status });
  }
}
