import { getPriority1Config } from "@/lib/p1-config";

export class Priority1Error extends Error {
  status: number;
  messages: string[];

  constructor(status: number, messages: string[]) {
    super(messages[0] || `Rating request failed (${status}).`);
    this.name = "Priority1Error";
    this.status = status;
    this.messages = messages;
  }
}

type MessageLike = { text?: string | null; severity?: string | null };

function collectMessages(body: unknown): string[] {
  const from = (entry: unknown): string | null => {
    if (!entry || typeof entry !== "object") return null;
    const text = (entry as MessageLike).text;
    return typeof text === "string" && text.trim() ? text.trim() : null;
  };
  if (Array.isArray(body)) {
    return body.map(from).filter((text): text is string => Boolean(text));
  }
  const single = from(body);
  return single ? [single] : [];
}

function scrub(text: string, secret: string): string {
  if (!secret) return text;
  return text.split(secret).join("[redacted]");
}

export async function postPriority1(path: string, body: unknown): Promise<unknown> {
  const config = getPriority1Config();
  if (!config.apiKey) {
    throw new Priority1Error(401, ["No API key is configured."]);
  }

  const timeoutMs = 30_000;
  let response: Response;
  try {
    response = await fetch(`${config.baseUrl}${path}`, {
      method: "POST",
      headers: {
        "X-API-KEY": config.apiKey,
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : "network error";
    throw new Priority1Error(504, [`The rating service did not respond (${scrub(reason, config.apiKey)}).`]);
  }

  const rawText = await response.text();
  let parsed: unknown = null;
  if (rawText) {
    try {
      parsed = JSON.parse(rawText);
    } catch {
      parsed = null;
    }
  }

  if (!response.ok) {
    const messages = collectMessages(parsed).map((message) => scrub(message, config.apiKey));
    if (messages.length === 0) {
      if (response.status === 401) messages.push("The API key was rejected.");
      else if (response.status === 403) messages.push("This API key is not allowed to call that endpoint.");
      else if (response.status === 429) messages.push("The rating service is rate limiting requests. Try again shortly.");
      else messages.push(`The rating service returned ${response.status}.`);
    }
    throw new Priority1Error(response.status, messages);
  }

  if (!parsed || typeof parsed !== "object") {
    throw new Priority1Error(502, ["The rating service returned an unreadable response."]);
  }
  return parsed;
}

export function truckloadUnavailableMessage(error: Priority1Error): string | null {
  if (error.status === 401 || error.status === 403) {
    return "Truckload quoting is not available on this API key. Priority1 may not have enabled full truckload for the EasyPost account. LTL quoting is unaffected.";
  }
  return null;
}
