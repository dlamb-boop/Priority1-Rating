import { errorPayload, suggestClass } from "@/lib/quote-service";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: Request) {
  let body: { totalWeight: number; length: number; width: number; height: number; units: number };
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Send a JSON request." }, { status: 400 });
  }
  try {
    const result = await suggestClass(body);
    return Response.json(result);
  } catch (error) {
    const payload = errorPayload(error);
    return Response.json(payload.body, { status: payload.status });
  }
}
