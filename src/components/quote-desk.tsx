"use client";

import { useEffect, useMemo, useState } from "react";
import { ACCESSORIAL_GROUPS, ACCESSORIALS } from "@/lib/accessorials";
import {
  EQUIPMENT_LABELS,
  EQUIPMENT_TYPES,
  FREIGHT_CLASSES,
  PACKAGING_TYPES,
  type EquipmentType,
  type FreightClass,
  type PackagingType,
} from "@/lib/constants";
import { toCustomerRate } from "@/lib/customer-quote";
import {
  formatLongDate,
  formatMoney,
  formatPercent,
  formatServiceLevel,
  formatShortDate,
  formatTransitDays,
  nextBusinessDay,
} from "@/lib/format";
import type { DeskRate, LineItemInput, QuoteDeskResponse, ShipmentSummary } from "@/lib/types";
import { MARKUP_DEFAULT, MARKUP_MAX, MARKUP_MIN } from "@/lib/markup";

type ItemDraft = LineItemInput & { key: string; suggestion?: string };

type Health = { mode: "mock" | "live"; modeLabel: string };

function newItem(overrides: Partial<ItemDraft> = {}): ItemDraft {
  return {
    key: Math.random().toString(36).slice(2, 10),
    freightClass: "70",
    packagingType: "Pallet",
    units: 1,
    pieces: 1,
    totalWeight: 500,
    length: 48,
    width: 40,
    height: 48,
    isStackable: false,
    isHazardous: false,
    isUsed: false,
    isMachinery: false,
    nmfcItemCode: "",
    nmfcSubCode: "",
    description: "",
    ...overrides,
  };
}

function place(summary: ShipmentSummary, side: "origin" | "destination"): string {
  if (side === "origin") {
    const city = [summary.originCity, summary.originState].filter(Boolean).join(", ");
    return city ? `${city} ${summary.originZipCode}` : summary.originZipCode;
  }
  const city = [summary.destinationCity, summary.destinationState].filter(Boolean).join(", ");
  return city ? `${city} ${summary.destinationZipCode}` : summary.destinationZipCode;
}

export function QuoteDesk() {
  const [product, setProduct] = useState<"ltl" | "tl">("ltl");
  const [health, setHealth] = useState<Health | null>(null);
  const [customerName, setCustomerName] = useState("");
  const [company, setCompany] = useState("");
  const [originZip, setOriginZip] = useState("");
  const [originCity, setOriginCity] = useState("");
  const [originState, setOriginState] = useState("");
  const [destZip, setDestZip] = useState("");
  const [destCity, setDestCity] = useState("");
  const [destState, setDestState] = useState("");
  const [pickupDate, setPickupDate] = useState(nextBusinessDay());
  const [items, setItems] = useState<ItemDraft[]>([newItem()]);
  const [accessorials, setAccessorials] = useState<string[]>([]);
  const [accessorialQuery, setAccessorialQuery] = useState("");
  const [markup, setMarkup] = useState(MARKUP_DEFAULT);
  const [equipment, setEquipment] = useState<EquipmentType>("53_Foot_Dry_Van");
  const [serviceType, setServiceType] = useState<"Full" | "Team">("Full");
  const [weight, setWeight] = useState(12000);
  const [pallets, setPallets] = useState(12);
  const [description, setDescription] = useState("");
  const [liftGate, setLiftGate] = useState(false);
  const [busy, setBusy] = useState(false);
  const [suggestingKey, setSuggestingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [quote, setQuote] = useState<QuoteDeskResponse | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [showInternal, setShowInternal] = useState(false);
  const [showPriority1, setShowPriority1] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);

  useEffect(() => {
    fetch("/api/health")
      .then((response) => response.json())
      .then((body: Health) => setHealth(body))
      .catch(() => setHealth(null));
  }, []);

  const filteredAccessorials = useMemo(() => {
    const query = accessorialQuery.trim().toLowerCase();
    return ACCESSORIALS.filter((item) => {
      if (!query) return true;
      return item.code.toLowerCase().includes(query) || item.description.toLowerCase().includes(query);
    });
  }, [accessorialQuery]);

  function loadSample() {
    setCustomerName("Alex Chen");
    setCompany("Northwind Goods");
    setOriginZip("72205");
    setOriginCity("Little Rock");
    setOriginState("AR");
    setDestZip("60606");
    setDestCity("Chicago");
    setDestState("IL");
    setPickupDate(nextBusinessDay());
    setMarkup(MARKUP_DEFAULT);
    setAccessorials(["LGPU", "APPT"]);
    setItems([
      newItem({
        freightClass: "70",
        packagingType: "Pallet",
        units: 1,
        pieces: 1,
        totalWeight: 500,
        length: 48,
        width: 40,
        height: 48,
        description: "Packaged hardware",
      }),
    ]);
    setEquipment("53_Foot_Dry_Van");
    setWeight(18000);
    setPallets(20);
    setDescription("Packaged hardware");
    setError(null);
  }

  function updateItem(key: string, patch: Partial<ItemDraft>) {
    setItems((current) => current.map((item) => (item.key === key ? { ...item, ...patch } : item)));
  }

  async function suggestClass(item: ItemDraft) {
    setSuggestingKey(item.key);
    setError(null);
    try {
      const response = await fetch("/api/ltl/suggested-class", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          totalWeight: Number(item.totalWeight),
          length: Number(item.length),
          width: Number(item.width),
          height: Number(item.height),
          units: Number(item.units),
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Could not suggest a class.");
      updateItem(item.key, { freightClass: body.suggestedClass as FreightClass, suggestion: body.suggestedClass });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not suggest a class.");
    } finally {
      setSuggestingKey(null);
    }
  }

  async function getRates() {
    setBusy(true);
    setError(null);
    try {
      const payload =
        product === "ltl"
          ? {
              markupPercent: markup,
              originZipCode: originZip,
              originCity,
              originStateAbbreviation: originState,
              destinationZipCode: destZip,
              destinationCity: destCity,
              destinationStateAbbreviation: destState,
              pickupDate,
              accessorialServices: accessorials,
              items: items.map(({ key: _key, suggestion: _suggestion, ...item }) => ({
                ...item,
                units: Number(item.units),
                pieces: item.pieces === null || item.pieces === undefined ? null : Number(item.pieces),
                totalWeight: Number(item.totalWeight),
                length: Number(item.length),
                width: Number(item.width),
                height: Number(item.height),
              })),
            }
          : {
              markupPercent: markup,
              originZipCode: originZip,
              originCity,
              originState,
              destinationZipCode: destZip,
              destinationCity: destCity,
              destinationState: destState,
              pickupDateOpen: pickupDate,
              equipment,
              truckloadQuoteServiceTypeId: serviceType,
              weight: Number(weight),
              weightUnitId: "lbs",
              palletCount: Number(pallets),
              description,
              requiresLiftGate: liftGate,
              startTime: "08:00",
              endTime: "17:00",
            };
      const response = await fetch(product === "ltl" ? "/api/ltl/rates" : "/api/tl/rates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "The quote failed.");
      const next = body as QuoteDeskResponse;
      setQuote(next);
      setShowInternal(false);
      const picks: Record<string, boolean> = {};
      next.rates.forEach((rate) => {
        picks[rate.optionId] = true;
      });
      setSelected(picks);
    } catch (reason) {
      setQuote(null);
      setError(reason instanceof Error ? reason.message : "The quote failed.");
    } finally {
      setBusy(false);
    }
  }

  async function downloadPdf() {
    if (!quote) return;
    const options = quote.rates.filter((rate) => selected[rate.optionId]).map(toCustomerRate);
    if (options.length === 0) {
      setError("Choose at least one option to include on the quote.");
      return;
    }
    setPdfBusy(true);
    setError(null);
    try {
      const response = await fetch("/api/quotes/pdf", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          customerName,
          company,
          showPriority1,
          shipment: quote.shipment,
          options,
        }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({ error: "The PDF could not be created." }));
        throw new Error(body.error || "The PDF could not be created.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const header = response.headers.get("Content-Disposition") || "";
      const match = /filename="([^"]+)"/.exec(header);
      link.href = url;
      link.download = match?.[1] || "EasyPost-Freight-Quote.pdf";
      link.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The PDF could not be created.");
    } finally {
      setPdfBusy(false);
    }
  }

  const straightOrSprinter = equipment.includes("Straight") || equipment === "Sprinter_Van";

  return (
    <main className="desk">
      <header className="topbar">
        <div className="brand">
          <div className="mark">E</div>
          <div>
            <div className="brand-name">EasyPost</div>
            <div className="brand-sub">Freight quote desk</div>
          </div>
        </div>
        <div className="who">
          <span className={health?.mode === "live" ? "badge live" : "badge"}>{health?.modeLabel ?? "Checking mode"}</span>
          <span>Dawson Lamb</span>
        </div>
      </header>

      <section className="hero">
        <div>
          <h1>Quote freight without leaving the desk.</h1>
          <p>
            Shop LTL rates, and truckload when the account allows it. Customer quotes show the sell price only.
          </p>
        </div>
        <div className="tabs" role="tablist">
          <button type="button" role="tab" aria-selected={product === "ltl"} onClick={() => setProduct("ltl")}>
            LTL
          </button>
          <button type="button" role="tab" aria-selected={product === "tl"} onClick={() => setProduct("tl")}>
            Truckload
          </button>
        </div>
      </section>

      <div className="stack">
        <section className="card">
          <div className="section-label">
            <h2>{product === "ltl" ? "LTL shipment" : "Truckload shipment"}</h2>
            <button type="button" className="tiny" onClick={loadSample} id="load-sample">
              Load sample lane
            </button>
          </div>
          <div className="grid-2">
            <label className="field">
              Customer name
              <input value={customerName} onChange={(event) => setCustomerName(event.target.value)} placeholder="Alex Chen" />
            </label>
            <label className="field">
              Company
              <input value={company} onChange={(event) => setCompany(event.target.value)} placeholder="Northwind Goods" />
            </label>
          </div>
          <div className="grid-2" style={{ marginTop: 12 }}>
            <div className="grid-3">
              <label className="field">
                Origin ZIP
                <input value={originZip} onChange={(event) => setOriginZip(event.target.value)} placeholder="72205" required />
              </label>
              <label className="field">
                City
                <input value={originCity} onChange={(event) => setOriginCity(event.target.value)} placeholder="Little Rock" />
              </label>
              <label className="field">
                State
                <input value={originState} onChange={(event) => setOriginState(event.target.value)} placeholder="AR" maxLength={2} />
              </label>
            </div>
            <div className="grid-3">
              <label className="field">
                Destination ZIP
                <input value={destZip} onChange={(event) => setDestZip(event.target.value)} placeholder="60606" required />
              </label>
              <label className="field">
                City
                <input value={destCity} onChange={(event) => setDestCity(event.target.value)} placeholder="Chicago" />
              </label>
              <label className="field">
                State
                <input value={destState} onChange={(event) => setDestState(event.target.value)} placeholder="IL" maxLength={2} />
              </label>
            </div>
          </div>
          <div className="grid-2" style={{ marginTop: 12 }}>
            <label className="field">
              {product === "ltl" ? "Pickup date" : "Pickup open date"}
              <input type="date" value={pickupDate} onChange={(event) => setPickupDate(event.target.value)} />
            </label>
            <label className="field">
              Markup
              <span className="hint">Applied server-side, from {MARKUP_MIN}% to {MARKUP_MAX}%. Default {MARKUP_DEFAULT}%.</span>
              <span className="markup">
                <input
                  type="range"
                  min={MARKUP_MIN}
                  max={MARKUP_MAX}
                  step={0.1}
                  value={markup}
                  aria-label="Markup percent"
                  onChange={(event) => setMarkup(Number(event.target.value))}
                />
                <input
                  type="number"
                  min={MARKUP_MIN}
                  max={MARKUP_MAX}
                  step={0.1}
                  value={markup}
                  aria-label="Markup percent value"
                  onChange={(event) => setMarkup(Number(event.target.value))}
                />
              </span>
            </label>
          </div>
        </section>

        {product === "ltl" ? (
          <section className="card">
            <div className="section-label">
              <h2>Line items</h2>
              <button type="button" className="tiny" onClick={() => setItems((current) => [...current, newItem()])}>
                Add item
              </button>
            </div>
            <div className="stack">
              {items.map((item, index) => (
                <div className="item-card" key={item.key}>
                  <div className="item-head">
                    <strong>Item {index + 1}</strong>
                    {items.length > 1 ? (
                      <button type="button" className="tiny" onClick={() => setItems((current) => current.filter((row) => row.key !== item.key))}>
                        Remove
                      </button>
                    ) : null}
                  </div>
                  <div className="grid-5">
                    <label className="field">
                      Freight class
                      <select
                        value={item.freightClass}
                        onChange={(event) => updateItem(item.key, { freightClass: event.target.value as FreightClass })}
                      >
                        {FREIGHT_CLASSES.map((value) => (
                          <option key={value}>{value}</option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      Packaging
                      <select
                        value={item.packagingType}
                        onChange={(event) => updateItem(item.key, { packagingType: event.target.value as PackagingType })}
                      >
                        {PACKAGING_TYPES.map((value) => (
                          <option key={value}>{value}</option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      Units
                      <input type="number" min={1} value={item.units} onChange={(event) => updateItem(item.key, { units: Number(event.target.value) })} />
                    </label>
                    <label className="field">
                      Pieces
                      <input type="number" min={1} value={item.pieces ?? ""} onChange={(event) => updateItem(item.key, { pieces: Number(event.target.value) })} />
                    </label>
                    <label className="field">
                      Total weight (lb)
                      <input type="number" min={1} value={item.totalWeight} onChange={(event) => updateItem(item.key, { totalWeight: Number(event.target.value) })} />
                    </label>
                  </div>
                  <div className="grid-5">
                    <label className="field">
                      Length (in)
                      <input type="number" min={1} value={item.length} onChange={(event) => updateItem(item.key, { length: Number(event.target.value) })} />
                    </label>
                    <label className="field">
                      Width (in)
                      <input type="number" min={1} value={item.width} onChange={(event) => updateItem(item.key, { width: Number(event.target.value) })} />
                    </label>
                    <label className="field">
                      Height (in)
                      <input type="number" min={1} value={item.height} onChange={(event) => updateItem(item.key, { height: Number(event.target.value) })} />
                    </label>
                    <label className="field">
                      Description
                      <input value={item.description ?? ""} onChange={(event) => updateItem(item.key, { description: event.target.value })} />
                    </label>
                    <label className="field">
                      Class helper
                      <button type="button" className="ghost" disabled={suggestingKey === item.key} onClick={() => suggestClass(item)}>
                        {suggestingKey === item.key ? "Checking…" : "Suggest class"}
                      </button>
                      {item.suggestion ? <span className="suggestion">Suggested {item.suggestion}</span> : null}
                    </label>
                  </div>
                  <div className="grid-2">
                    <label className="field">
                      NMFC item
                      <input value={item.nmfcItemCode ?? ""} onChange={(event) => updateItem(item.key, { nmfcItemCode: event.target.value })} />
                    </label>
                    <label className="field">
                      NMFC sub
                      <input value={item.nmfcSubCode ?? ""} onChange={(event) => updateItem(item.key, { nmfcSubCode: event.target.value })} />
                    </label>
                  </div>
                  <div className="checks">
                    <label>
                      <input type="checkbox" checked={Boolean(item.isStackable)} onChange={(event) => updateItem(item.key, { isStackable: event.target.checked })} />
                      Stackable
                    </label>
                    <label>
                      <input type="checkbox" checked={Boolean(item.isHazardous)} onChange={(event) => updateItem(item.key, { isHazardous: event.target.checked })} />
                      Hazmat
                    </label>
                    <label>
                      <input type="checkbox" checked={Boolean(item.isUsed)} onChange={(event) => updateItem(item.key, { isUsed: event.target.checked })} />
                      Used
                    </label>
                    <label>
                      <input type="checkbox" checked={Boolean(item.isMachinery)} onChange={(event) => updateItem(item.key, { isMachinery: event.target.checked })} />
                      Machinery
                    </label>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <section className="card">
            <div className="section-label">
              <h2>Equipment</h2>
              <p>Live truckload calls fail clearly if the key does not include truckload.</p>
            </div>
            <div className="grid-5">
              <label className="field">
                Equipment
                <select value={equipment} onChange={(event) => setEquipment(event.target.value as EquipmentType)}>
                  {EQUIPMENT_TYPES.map((value) => (
                    <option key={value} value={value}>
                      {EQUIPMENT_LABELS[value]}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                Service
                <select value={serviceType} onChange={(event) => setServiceType(event.target.value as "Full" | "Team")}>
                  <option value="Full">Full</option>
                  <option value="Team">Team</option>
                </select>
              </label>
              <label className="field">
                Weight (lb)
                <input type="number" min={1} value={weight} onChange={(event) => setWeight(Number(event.target.value))} />
              </label>
              <label className="field">
                Pallets
                <input type="number" min={1} value={pallets} onChange={(event) => setPallets(Number(event.target.value))} />
              </label>
              <label className="field">
                Commodity
                <input value={description} onChange={(event) => setDescription(event.target.value)} />
              </label>
            </div>
            {straightOrSprinter ? (
              <label className="switch" style={{ marginTop: 12 }}>
                <input type="checkbox" checked={liftGate} onChange={(event) => setLiftGate(event.target.checked)} />
                Lift gate required
              </label>
            ) : (
              <p className="hint" style={{ marginTop: 12 }}>
                Lift gate is only sent for straight trucks and sprinter vans, matching the API.
              </p>
            )}
          </section>
        )}

        {product === "ltl" ? (
          <section className="card accessorials">
            <div className="section-label">
              <h2>Accessorials</h2>
              <p>{accessorials.length} selected. Hazmat on a line item also sends HAZM.</p>
            </div>
            <div className="search">
              <input
                placeholder="Search codes or names"
                value={accessorialQuery}
                onChange={(event) => setAccessorialQuery(event.target.value)}
                aria-label="Search accessorials"
              />
            </div>
            {ACCESSORIAL_GROUPS.map((group) => {
              const rows = filteredAccessorials.filter((item) => item.group === group);
              if (rows.length === 0) return null;
              const body = (
                <div className="codes">
                  {rows.map((item) => (
                    <label key={item.code}>
                      <input
                        type="checkbox"
                        checked={accessorials.includes(item.code)}
                        onChange={(event) => {
                          setAccessorials((current) =>
                            event.target.checked
                              ? [...current, item.code]
                              : current.filter((code) => code !== item.code),
                          );
                        }}
                      />
                      {item.description}
                      <span className="scac">{item.code}</span>
                    </label>
                  ))}
                </div>
              );
              if (group === "Common" || accessorialQuery.trim()) {
                return (
                  <div className="group" key={group}>
                    <h3>{group}</h3>
                    {body}
                  </div>
                );
              }
              return (
                <details className="group" key={group}>
                  <summary>{group}</summary>
                  {body}
                </details>
              );
            })}
          </section>
        ) : null}

        <div className="actions">
          <p className="hint">
            {product === "tl"
              ? "Truckload responses do not include a carrier name or SCAC."
              : "Required: both ZIPs, a pickup date, and at least one line item."}
          </p>
          <button type="button" className="primary" id="get-rates" onClick={getRates} disabled={busy}>
            {busy ? "Rating carriers…" : "Get rates"}
          </button>
        </div>

        {error ? <div className="error">{error}</div> : null}

        {quote ? <RatesPanel
          quote={quote}
          selected={selected}
          setSelected={setSelected}
          showInternal={showInternal}
          setShowInternal={setShowInternal}
          showPriority1={showPriority1}
          setShowPriority1={setShowPriority1}
          pdfBusy={pdfBusy}
          onPdf={downloadPdf}
        /> : null}
      </div>
    </main>
  );
}

function RatesPanel({
  quote,
  selected,
  setSelected,
  showInternal,
  setShowInternal,
  showPriority1,
  setShowPriority1,
  pdfBusy,
  onPdf,
}: {
  quote: QuoteDeskResponse;
  selected: Record<string, boolean>;
  setSelected: (value: Record<string, boolean>) => void;
  showInternal: boolean;
  setShowInternal: (value: boolean) => void;
  showPriority1: boolean;
  setShowPriority1: (value: boolean) => void;
  pdfBusy: boolean;
  onPdf: () => void;
}) {
  return (
    <section className="card" id="rates-panel">
      <div className="rates-head">
        <div>
          <h2 style={{ margin: 0 }}>
            {place(quote.shipment, "origin")} → {place(quote.shipment, "destination")}
          </h2>
          <p className="hint" style={{ marginTop: 4 }}>
            Pickup {formatLongDate(quote.shipment.pickupDate)}
            {quote.shipment.totalWeight != null ? ` · ${quote.shipment.totalWeight.toLocaleString("en-US")} lb` : ""}
            {quote.shipment.distanceMiles != null ? ` · ${quote.shipment.distanceMiles.toLocaleString("en-US")} miles` : ""}
            {" · "}
            {quote.rates.length} option{quote.rates.length === 1 ? "" : "s"}, lowest price first
          </p>
        </div>
        <label className="switch">
          <input
            type="checkbox"
            checked={showInternal}
            onChange={(event) => setShowInternal(event.target.checked)}
          />
          Show internal costs
        </label>
      </div>

      {quote.warnings.map((warning) => (
        <div className="warning" key={warning} style={{ marginBottom: 8 }}>
          {warning}
        </div>
      ))}

      <div className="table-wrap">
        <table className="rates" id="rates-table">
          <thead>
            <tr>
              <th>Include</th>
              <th>Carrier</th>
              <th>SCAC</th>
              <th>Service</th>
              <th>Transit</th>
              <th>Est. delivery</th>
              <th>Expires</th>
              <th className="num">Customer price</th>
            </tr>
          </thead>
          <tbody>
            {quote.rates.map((rate) => (
              <tr key={rate.optionId}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`Include ${rate.carrierName}`}
                    checked={Boolean(selected[rate.optionId])}
                    onChange={(event) => setSelected({ ...selected, [rate.optionId]: event.target.checked })}
                  />
                </td>
                <td className="carrier">{rate.carrierName}</td>
                <td className="scac">{rate.scac || "—"}</td>
                <td>
                  {formatServiceLevel(rate.serviceLevel, rate.serviceLevelDescription)}
                  {rate.laneType ? (
                    <div className="hint">
                      {rate.laneType.charAt(0).toUpperCase() + rate.laneType.slice(1).toLowerCase()}
                    </div>
                  ) : null}
                </td>
                <td>{formatTransitDays(rate.transitDays)}</td>
                <td>{formatShortDate(rate.deliveryDate)}</td>
                <td>{formatShortDate(rate.expirationDate)}</td>
                <td className="num price">{formatMoney(rate.customerTotal, rate.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showInternal ? (
        <div className="internal">
          <h3>Internal only. These figures stay off the customer quote.</h3>
          <table>
            <thead>
              <tr>
                <th>Carrier</th>
                <th>Buy rate</th>
                <th>Markup</th>
                <th>Margin</th>
                <th>Carrier quote #</th>
              </tr>
            </thead>
            <tbody>
              {quote.rates.map((rate) => (
                <tr key={rate.optionId}>
                  <td>{rate.carrierName}</td>
                  <td>{formatMoney(rate.internal.baseTotal, rate.currency)}</td>
                  <td>
                    {formatMoney(rate.internal.markupAmount, rate.currency)} ({formatPercent(rate.internal.markupPercent)})
                  </td>
                  <td>{formatPercent(rate.internal.marginPercent)}</td>
                  <td className="scac">{rate.internal.carrierQuoteNumber || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {quote.failedCarriers.length > 0 ? (
        <div className="failed">
          <strong>No rate returned</strong>
          <ul>
            {quote.failedCarriers.map((failed) => (
              <li key={`${failed.scac}-${failed.carrierName}`}>
                {failed.carrierName}
                {failed.scac ? ` (${failed.scac})` : ""}: {failed.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="pdf-bar">
        <label className="switch">
          <input type="checkbox" checked={showPriority1} onChange={(event) => setShowPriority1(event.target.checked)} />
          Mention Priority1 on the customer PDF
        </label>
        <button type="button" className="primary" id="download-pdf" onClick={onPdf} disabled={pdfBusy}>
          {pdfBusy ? "Preparing PDF…" : "Download customer PDF"}
        </button>
      </div>
    </section>
  );
}
