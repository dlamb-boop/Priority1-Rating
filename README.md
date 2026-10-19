# EasyPost Freight Quotes

Internal rating desk for Dawson Lamb. It quotes LTL freight (and truckload, when the account allows it) through Priority1, applies a hidden 5–10% markup, and exports a customer-facing PDF that shows only the sell price.

No API key is required to try it. With `P1_API_KEY` empty, the app runs in demo mode and returns realistic sample rates.

## Run locally

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

```bash
npm test          # markup math and customer-PDF safety
npm run lint      # TypeScript check
npm run sample-pdf
```

## Environment

| Variable | Purpose |
| --- | --- |
| `P1_API_KEY` | Priority1 key, sent only as the `X-API-KEY` header from the server. Leave blank for demo mode. |
| `P1_BASE_URL` | `https://dev-api.priority1.com` (sandbox, the default) or `https://api.priority1.com` (production). |
| `P1_MOCK` | Set to `true` to force demo rates even when a key is present. |

The browser never receives the key, the raw Priority1 payload, or upstream quote ids. Copy `.env.example` to `.env.local`. Do not commit `.env.local`.

### Sandbox and production

Demo (no key):

```bash
P1_API_KEY=
P1_BASE_URL=https://dev-api.priority1.com
```

Sandbox:

```bash
P1_API_KEY=your-sandbox-key
P1_BASE_URL=https://dev-api.priority1.com
P1_MOCK=false
```

Production:

```bash
P1_API_KEY=your-production-key
P1_BASE_URL=https://api.priority1.com
P1_MOCK=false
```

Live rate calls can take up to about 15 seconds because Priority1 waits on each carrier (`apiConfiguration.timeout`, default 15). The server allows 30 seconds for the round trip.

## What the desk does

- LTL quote: origin and destination ZIP, pickup date, one or more line items (class, packaging, units, total weight, dimensions, plus stackable, hazmat, used, machinery, NMFC, and description). Accessorials use Priority1's published codes and names. **Suggest class** calls `POST /v2/ltl/quotes/suggestedclass`.
- Markup slider from 5% to 10%, default 7%. The server rejects anything outside that range, marks up the carrier total, and scales itemized charges by the same factor so they still add up to the customer price (rounded to the cent).
- Rates table sorted by customer price. **Show internal costs** is off by default and is the only place buy rate, markup dollars, margin, and the carrier quote number appear.
- Customer PDF for the options you check. It includes the customer, the shipment, sell prices, the quote date and validity, and “Prepared by Dawson Lamb, Director of Supply Chain Solutions and Partnerships, EasyPost”. Priority1 is omitted unless **Mention Priority1 on the customer PDF** is checked. The filename is `EasyPost-Freight-Quote-YYYY-MM-DD.pdf`.
- Truckload is a second tab (`POST /v2/tl/truckloadquotes/rates`). Those responses have no carrier name or SCAC. If the key is not enabled for truckload, the tab shows that error and LTL keeps working.

## Deploy

Any Node 22 host that can run a Next.js app is enough. Set the env vars above in the host, not in the image.

```bash
npm install
npm run build
npm start
```

A `Dockerfile` is included. It does not copy env files. Pass `P1_API_KEY` and `P1_BASE_URL` at runtime.

This desk has no login. Keep it on an internal network.

## Spec notes

Field names follow the v2 OpenAPI spec (`POST /v2/ltl/quotes/rates`, `POST /v2/ltl/quotes/suggestedclass`, `POST /v2/tl/truckloadquotes/rates`).

- LTL `pickupDate` is sent as origin-local `YYYY-MM-DDT00:00:00` with no `Z`. The truckload example in the spec uses an offset (`+00:00`) while the field description says the origin timezone. This app sends truckload `pickupDateOpen` the same way as LTL, without a `Z` or numeric offset.
- `freightClass` is a string (`"70"`, `"77.5"`). `totalWeight` is pounds for the whole line, not per unit.
- The published R&L example has itemized charges that do not add up to `rateQuoteDetail.total`. The desk adds an “Other charges” line after markup so the customer breakdown matches the price.
- `rateQuoteDetail.baseCost` is in the schema and missing from the example. The sell price is the marked-up `total`. When `baseCost` is present it is shown only in the internal panel.
- Truckload’s only schema-required field is `pickupDateOpen`. The desk also requires origin and destination ZIPs. Carrier name and SCAC are not in the response, so options are labeled “Truckload option 1” and so on.
- Hazmat at quote time is `items[].isHazardous` plus the `HAZM` accessorial. Full hazmat details are a dispatch concern and are not collected here.
- Enhanced handling units (mixed class on one pallet) are optional in the spec and are not on this form. Standard `items[]` covers the required quote.
