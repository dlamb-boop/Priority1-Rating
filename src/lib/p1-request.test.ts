import { describe, expect, it } from "vitest";
import { buildLtlRatesRequest, buildSuggestedClassRequest, buildTlRatesRequest } from "@/lib/p1-request";
import type { LtlQuoteInput, TlQuoteInput } from "@/lib/types";

const ltl: LtlQuoteInput = {
  markupPercent: 7,
  originZipCode: "72205",
  destinationZipCode: "60606",
  pickupDate: "2026-10-20",
  items: [
    {
      freightClass: "150",
      packagingType: "Pallet",
      units: 1,
      pieces: 1,
      totalWeight: 275,
      length: 48,
      width: 40,
      height: 40,
      isStackable: false,
      isHazardous: false,
      isUsed: false,
      isMachinery: false,
    },
  ],
  accessorialServices: ["LGPU", "APPT"],
};

describe("Priority1 request mapping", () => {
  it("matches the LTL rates schema and leaves desk-only fields out", () => {
    const body = buildLtlRatesRequest(ltl);
    expect(body).toEqual({
      originZipCode: "72205",
      destinationZipCode: "60606",
      pickupDate: "2026-10-20T00:00:00",
      items: [
        {
          freightClass: "150",
          packagingType: "Pallet",
          units: 1,
          pieces: 1,
          totalWeight: 275,
          length: 48,
          width: 40,
          height: 40,
          isStackable: false,
          isHazardous: false,
          isUsed: false,
          isMachinery: false,
        },
      ],
      accessorialServices: [{ code: "LGPU" }, { code: "APPT" }],
    });
    expect(JSON.stringify(body)).not.toContain("markup");
    expect(body.pickupDate).not.toContain("Z");
  });

  it("matches the suggested-class schema", () => {
    expect(
      buildSuggestedClassRequest({ totalWeight: 200, width: 100, height: 100, length: 100, units: 1 }),
    ).toEqual({
      totalWeight: 200,
      length: 100,
      width: 100,
      height: 100,
      units: 1,
    });
  });

  it("matches the truckload rates schema with an origin-local open date", () => {
    const input: TlQuoteInput = {
      markupPercent: 7,
      originZipCode: "90221",
      originCity: "Los Angeles",
      originState: "CA",
      destinationZipCode: "72205",
      destinationCity: "Little Rock",
      destinationState: "AR",
      pickupDateOpen: "2026-10-20",
      equipment: "53_Foot_Dry_Van",
      truckloadQuoteServiceTypeId: "Full",
      weight: 100,
      weightUnitId: "lbs",
      palletCount: 3,
      description: "Olives",
      startTime: "08:00",
      endTime: "20:00",
    };
    const body = buildTlRatesRequest(input);
    expect(body.pickupDateOpen).toBe("2026-10-20T00:00:00");
    expect(body.equipment).toBe("53_Foot_Dry_Van");
    expect(body.truckloadQuoteServiceTypeId).toBe("Full");
    expect(body.weightUnitId).toBe("lbs");
    expect(body).not.toHaveProperty("markupPercent");
    expect(String(body.pickupDateOpen)).not.toMatch(/Z|[+-]\d{2}:\d{2}$/);
  });
});
