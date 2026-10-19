# EasyPost Freight Quotes

Internal rating desk for Dawson Lamb. It quotes LTL freight (and truckload, when the account allows it), applies a hidden 5–10% markup, and exports a customer-facing PDF that shows only the sell price.

The app is a Streamlit desk meant for [Streamlit Community Cloud](https://share.streamlit.io). It loads directly, with no password. No API key is required to try it. With `P1_API_KEY` empty, the app runs in demo mode and returns realistic sample rates. The API key stays in Streamlit secrets and is never shown in the UI.

## Brand

Colors are sampled from the opaque pixels of the EasyPost wordmark and the August 2026 sales deck (*Intro EasyPost Suite Sales Presentation Extended*).

| Role | Hex | Used for |
| --- | --- | --- |
| Primary blue | `#164DFF` | Theme `primaryColor`, buttons, PDF rule, the E in the wordmark |
| Navy ink | `#061242` | Theme `textColor`, wordmark lettering, PDF headings |
| White | `#FFFFFF` | Theme `backgroundColor`, page background |
| Periwinkle wash | `#E8EDFF` | Theme `secondaryBackgroundColor`, sidebar, PDF header |
| Periwinkle band | `#D0DAFE` | PDF option borders |
| Mint | `#CBF9EE` | Mode chip, PDF table header |
| Lilac | `#EAD6FB` | Internal-only costs panel |
| Muted ink | `#3C4A78` | Captions and secondary PDF text |

Typography follows the deck: Poppins (400 / 500 / 600 / 700), loaded in the app from Google Fonts and embedded in the PDF from `assets/fonts`. Streamlit’s theme `font` key only accepts a generic family, so `.streamlit/config.toml` sets `sans serif` and the stylesheet applies Poppins.

The logo in `assets/easypost-logo.png` is the deck’s embedded wordmark (1600×370) with its soft mask kept as a transparent PNG. The deck does not include a vector logo.

## Run locally

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run streamlit_app.py
```

Open the URL Streamlit prints (usually http://localhost:8501). The quote form loads immediately.

Demo mode with environment variables, and no secrets file:

```bash
export P1_API_KEY=
export P1_BASE_URL=https://dev-api.priority1.com
export P1_MOCK=true
streamlit run streamlit_app.py
```

```bash
pytest
```

## Settings

Streamlit secrets win. If a key is absent there, the same name is read from the environment.

| Name | Purpose |
| --- | --- |
| `P1_API_KEY` | Priority1 key, sent only as the `X-API-KEY` header. Leave blank for demo mode. Stays in Streamlit secrets and is never shown in the UI. |
| `P1_BASE_URL` | `https://dev-api.priority1.com` (sandbox, the default) or `https://api.priority1.com` (production). |
| `P1_MOCK` | `true` forces demo rates even when a key is present. |
| `GOOGLE_PLACES_API_KEY` | Optional. When set, company lookup uses Google Places for the headquarters address and website. Leave blank to use Wikidata and the company website only. The key is never shown. |

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`. Do not commit `secrets.toml`.

### Sandbox and production

Demo (no key):

```toml
P1_API_KEY = ""
P1_BASE_URL = "https://dev-api.priority1.com"
P1_MOCK = "true"
```

Sandbox:

```toml
P1_API_KEY = "your-sandbox-key"
P1_BASE_URL = "https://dev-api.priority1.com"
P1_MOCK = "false"
```

Production:

```toml
P1_API_KEY = "your-production-key"
P1_BASE_URL = "https://api.priority1.com"
P1_MOCK = "false"
```

Live rate calls can take up to about 15 seconds because Priority1 waits on each carrier (`apiConfiguration.timeout`, default 15). The client allows 30 seconds for the round trip.

## What the desk does

- LTL quote: origin and destination ZIP, pickup date, one or more line items (class, packaging, units, total weight, dimensions, plus stackable, hazmat, used, machinery, NMFC, and description). Accessorials use Priority1's published codes and names. **Suggest class** calls `POST /v2/ltl/quotes/suggestedclass`.
- Markup slider from 5% to 10%, default 7%. The code rejects anything outside that range, marks up the carrier total, and scales itemized charges by the same factor so they still add up to the customer price (rounded half-up to the cent).
- Rates table sorted by customer price. **Show internal costs** is off by default and is the only place buy rate, markup dollars, margin, and the carrier quote number appear.
- Customer company: type the company name and press **Look up**. The desk fills the website, logo, and address. If several companies match, pick one from the list (name, city, and domain). The filled fields stay visible and can be corrected under **Edit details**. If nothing is found, the address is left blank. A domain is never invented from the name.
- Lookup order, with short timeouts: Wikidata (official website, logo, and headquarters), then the company homepage and, if needed, `/contact` or `/about` for a schema.org address and logo, then the site icon and a favicon service. When `GOOGLE_PLACES_API_KEY` is set, Google Places is the first source for the address and website.
- Customer PDF for the options you check. It includes the EasyPost logo, the customer, the looked-up company address, the customer logo when one was found, the shipment, sell prices, the quote date and validity, and a prepared-by line on every page. That line uses the name, title, email, and phone entered on the form, always ends with EasyPost, and leaves out anything left blank. The website URL is not printed. Priority1 is omitted unless **Mention Priority1 on the customer PDF** is checked. The filename is `EasyPost-Freight-Quote-YYYY-MM-DD.pdf`.
- Truckload is a second tab (`POST /v2/tl/truckloadquotes/rates`). Those responses have no carrier name or SCAC. If the key is not enabled for truckload, the tab says so and LTL keeps working.

## Deploy on Streamlit Community Cloud

1. Sign in at [share.streamlit.io](https://share.streamlit.io) and choose **Create app**.
2. Point it at this GitHub repo (`dlamb-boop/Priority1-Rating`) and the branch you want to run (this branch, or `main` after it is merged).
3. Set **Main file path** to `streamlit_app.py`.
4. Open **Advanced settings** and set **Python version** to **3.12**. `runtime.txt` also requests `python-3.12`.
5. Paste secrets into the **Secrets** box (the same keys as `.streamlit/secrets.toml.example`):

   ```toml
   P1_API_KEY = ""
   P1_BASE_URL = "https://dev-api.priority1.com"
   P1_MOCK = "true"
   ```

   Leave `P1_API_KEY` blank for demo rates. For live rates, paste the sandbox or production key, set `P1_BASE_URL` to match, and set `P1_MOCK` to `"false"`. The key stays in this secrets box and is never shown in the UI.
6. Deploy. Sharing can be left public.

## Spec notes

Field names follow the v2 OpenAPI spec (`POST /v2/ltl/quotes/rates`, `POST /v2/ltl/quotes/suggestedclass`, `POST /v2/tl/truckloadquotes/rates`).

- LTL `pickupDate` is sent as origin-local `YYYY-MM-DDT00:00:00` with no `Z`. The truckload example in the spec uses an offset (`+00:00`) while the field description says the origin timezone. This app sends truckload `pickupDateOpen` the same way as LTL, without a `Z` or numeric offset.
- `freightClass` is a string (`"70"`, `"77.5"`). `totalWeight` is pounds for the whole line, not per unit.
- The published R&L example has itemized charges that do not add up to `rateQuoteDetail.total`. The desk adds an “Other charges” line after markup so the customer breakdown matches the price.
- `rateQuoteDetail.baseCost` is in the schema and missing from the example. The sell price is the marked-up `total`. When `baseCost` is present it is shown only in the internal panel.
- Truckload’s only schema-required field is `pickupDateOpen`. The desk also requires origin and destination ZIPs. Carrier name and SCAC are not in the response, so options are labeled “Truckload option 1” and so on.
- Hazmat at quote time is `items[].isHazardous` plus the `HAZM` accessorial. Full hazmat details are a dispatch concern and are not collected here.
- Enhanced handling units (mixed class on one pallet) are optional in the spec and are not on this form. Standard `items[]` covers the required quote.
