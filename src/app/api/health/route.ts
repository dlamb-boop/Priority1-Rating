import { getPriority1Config, modeLabel } from "@/lib/p1-config";

export const dynamic = "force-dynamic";

export function GET() {
  const config = getPriority1Config();
  return Response.json({
    ok: true,
    mode: config.mock ? "mock" : "live",
    environment: config.environment,
    modeLabel: modeLabel(config),
  });
}
