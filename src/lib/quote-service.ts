import { mapLtlResponse, mapTlResponse } from "@/lib/map-rates";
import { mockLtlRates, mockTlRates, suggestFreightClass } from "@/lib/mock-rates";
import { getPriority1Config, modeLabel } from "@/lib/p1-config";
import { postPriority1, Priority1Error, truckloadUnavailableMessage } from "@/lib/p1-client";
import { buildLtlRatesRequest, buildSuggestedClassRequest, buildTlRatesRequest } from "@/lib/p1-request";
import type { LtlQuoteInput, QuoteDeskResponse, TlQuoteInput } from "@/lib/types";
import { MarkupError, normalizeMarkupPercent } from "@/lib/markup";
import { normalizeLtlInput, normalizeTlInput, QuoteInputError } from "@/lib/validation";

function meta() {
  const config = getPriority1Config();
  return {
    mode: config.mock ? ("mock" as const) : ("live" as const),
    environment: config.environment,
    modeLabel: modeLabel(config),
  };
}

export async function quoteLtl(raw: LtlQuoteInput): Promise<QuoteDeskResponse> {
  const input = normalizeLtlInput(raw);
  input.markupPercent = normalizeMarkupPercent(raw.markupPercent);
  const info = meta();
  const request = buildLtlRatesRequest(input);
  const upstream = info.mode === "mock" ? mockLtlRates(input) : await postPriority1("/v2/ltl/quotes/rates", request);
  return mapLtlResponse(upstream as never, input, info);
}

export async function quoteTl(raw: TlQuoteInput): Promise<QuoteDeskResponse> {
  const input = normalizeTlInput(raw);
  input.markupPercent = normalizeMarkupPercent(raw.markupPercent);
  const info = meta();
  if (info.mode === "mock") {
    return mapTlResponse(mockTlRates(input) as never, input, info);
  }
  try {
    const upstream = await postPriority1("/v2/tl/truckloadquotes/rates", buildTlRatesRequest(input));
    return mapTlResponse(upstream as never, input, info);
  } catch (error) {
    if (error instanceof Priority1Error) {
      const friendly = truckloadUnavailableMessage(error);
      if (friendly) {
        throw new QuoteInputError(friendly);
      }
    }
    throw error;
  }
}

export async function suggestClass(raw: {
  totalWeight: number;
  length: number;
  width: number;
  height: number;
  units: number;
}): Promise<{ suggestedClass: string; mode: "mock" | "live" }> {
  const request = buildSuggestedClassRequest({
    totalWeight: Number(raw.totalWeight),
    length: Number(raw.length),
    width: Number(raw.width),
    height: Number(raw.height),
    units: Number(raw.units),
  });
  for (const [key, value] of Object.entries(request)) {
    if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
      throw new QuoteInputError(`Enter ${key} before suggesting a class.`);
    }
  }
  const info = meta();
  if (info.mode === "mock") {
    return {
      suggestedClass: suggestFreightClass(request as never),
      mode: "mock",
    };
  }
  const upstream = (await postPriority1("/v2/ltl/quotes/suggestedclass", request)) as {
    suggestedClass?: string | null;
  };
  const suggestedClass = upstream.suggestedClass?.trim();
  if (!suggestedClass) {
    throw new Priority1Error(502, ["No freight class was suggested."]);
  }
  return { suggestedClass, mode: "live" };
}

export function errorPayload(error: unknown): { status: number; body: { error: string } } {
  if (error instanceof QuoteInputError || error instanceof MarkupError) {
    return { status: 400, body: { error: error.message } };
  }
  if (error instanceof Priority1Error) {
    const status = error.status === 429 ? 429 : error.status >= 500 ? 502 : error.status;
    return { status, body: { error: error.messages.join(" ") } };
  }
  return { status: 500, body: { error: "The quote could not be completed." } };
}
