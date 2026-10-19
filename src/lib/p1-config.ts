export type Priority1Config = {
  baseUrl: string;
  apiKey: string;
  mock: boolean;
  environment: "sandbox" | "production" | "custom";
};

const SANDBOX = "https://dev-api.priority1.com";
const PRODUCTION = "https://api.priority1.com";

export function getPriority1Config(env: NodeJS.ProcessEnv = process.env): Priority1Config {
  const baseUrl = (env.P1_BASE_URL || SANDBOX).trim().replace(/\/$/, "");
  const apiKey = (env.P1_API_KEY || "").trim();
  const forceMock = /^(1|true|yes)$/i.test((env.P1_MOCK || "").trim());
  const mock = forceMock || apiKey.length === 0;
  let environment: Priority1Config["environment"] = "custom";
  if (baseUrl === SANDBOX) environment = "sandbox";
  else if (baseUrl === PRODUCTION) environment = "production";
  return { baseUrl, apiKey, mock, environment };
}

export function modeLabel(config: Pick<Priority1Config, "mock" | "environment">): string {
  if (config.mock) return "Demo rates";
  if (config.environment === "production") return "Production";
  if (config.environment === "sandbox") return "Sandbox";
  return "Custom endpoint";
}
