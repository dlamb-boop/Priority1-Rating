export type ZipHint = { city: string; state: string };

/** A small hint table for the demo and for empty city fields. Not a rating source. */
const HINTS: Record<string, ZipHint> = {
  "02101": { city: "Boston", state: "MA" },
  "10001": { city: "New York", state: "NY" },
  "19103": { city: "Philadelphia", state: "PA" },
  "30303": { city: "Atlanta", state: "GA" },
  "33101": { city: "Miami", state: "FL" },
  "60606": { city: "Chicago", state: "IL" },
  "64101": { city: "Kansas City", state: "MO" },
  "72205": { city: "Little Rock", state: "AR" },
  "75201": { city: "Dallas", state: "TX" },
  "77002": { city: "Houston", state: "TX" },
  "80202": { city: "Denver", state: "CO" },
  "85001": { city: "Phoenix", state: "AZ" },
  "90221": { city: "Los Angeles", state: "CA" },
  "94105": { city: "San Francisco", state: "CA" },
  "98101": { city: "Seattle", state: "WA" },
};

export function zipHint(zip: string): ZipHint | undefined {
  const key = zip.trim().slice(0, 5);
  return HINTS[key];
}
