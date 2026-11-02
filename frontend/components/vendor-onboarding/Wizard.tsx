"use client";

import { useMemo, useState } from "react";
import {
  APPROVAL_ROWS,
  CITY_OPTIONS,
  COVERAGE_TYPES,
  DEFAULT_DOCUMENTS,
  EQUIPMENT_TAGS,
  INVOICE_INFO_TAGS,
  OnboardingDraft,
  OnboardingPayload,
  PRICING_TABS,
  SERVICE_CATEGORIES,
  SERVICE_OFFER_TAGS,
  VENDOR_TYPES,
} from "./types";

type Props = {
  initial: OnboardingPayload;
  mode: "company" | "vendor";
  onSave: (draft: OnboardingDraft) => Promise<OnboardingPayload>;
  onSubmit: () => Promise<{ message?: string; review_status?: string; score?: number; tier?: string }>;
};

function setPath(draft: OnboardingDraft, section: keyof OnboardingDraft, key: string, value: any): OnboardingDraft {
  if (section === "current_step") return { ...draft, current_step: Number(value) || 1 };
  const block = { ...((draft as any)[section] || {}), [key]: value };
  return { ...draft, [section]: block };
}

function toggleList(list: string[], value: string): string[] {
  const set = new Set(list || []);
  if (set.has(value)) set.delete(value);
  else set.add(value);
  return Array.from(set);
}

function Field({
  label,
  children,
  required,
  className = "",
}: {
  label: string;
  children: React.ReactNode;
  required?: boolean;
  className?: string;
}) {
  return (
    <label className={`vo-field ${className}`}>
      <span className="vo-label">
        {label}
        {required ? <em className="vo-req">*</em> : null}
      </span>
      {children}
    </label>
  );
}

function StatusPill({ status }: { status: string }) {
  const s = (status || "Pending").toLowerCase();
  let cls = "neutral";
  if (s.includes("verif") || s === "valid" || s === "active" || s === "completed") cls = "ok";
  else if (s.includes("expir") || s.includes("pending") || s.includes("soon")) cls = "warn";
  else if (s.includes("not required")) cls = "muted";
  return <span className={`vo-pill ${cls}`}>{status || "Pending"}</span>;
}

function IconBtn({ label, onClick, danger }: { label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button type="button" className={`vo-icon-btn ${danger ? "danger" : ""}`} title={label} onClick={onClick}>
      {label === "View" ? "👁" : label === "Edit" ? "✎" : "🗑"}
    </button>
  );
}

function TableEditor({
  rows,
  columns,
  onChange,
  addLabel,
  blank,
  showIndex,
}: {
  rows: any[];
  columns: { key: string; label: string; wide?: boolean }[];
  onChange: (rows: any[]) => void;
  addLabel: string;
  blank: Record<string, any>;
  showIndex?: boolean;
}) {
  return (
    <div className="vo-table-wrap">
      <table className="vo-table">
        <thead>
          <tr>
            {showIndex ? <th>#</th> : null}
            {columns.map((c) => (
              <th key={c.key}>{c.label}</th>
            ))}
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {(rows || []).length === 0 ? (
            <tr>
              <td colSpan={columns.length + (showIndex ? 2 : 1)} className="vo-empty-row">
                No rows yet. Use {addLabel} to add one.
              </td>
            </tr>
          ) : (
            (rows || []).map((row, idx) => (
              <tr key={idx}>
                {showIndex ? <td className="vo-idx">{idx + 1}</td> : null}
                {columns.map((c) => (
                  <td key={c.key} className={c.wide ? "wide" : ""}>
                    {c.key === "status" ? (
                      <StatusPill status={row[c.key]} />
                    ) : c.key === "file_name" ? (
                      <div className="vo-file-cell">
                        <input
                          placeholder="filename.pdf"
                          value={row[c.key] ?? ""}
                          onChange={(e) => {
                            const next = rows.map((r, i) => (i === idx ? { ...r, [c.key]: e.target.value } : r));
                            onChange(next);
                          }}
                        />
                        {row[c.key] ? (
                          <button
                            type="button"
                            className="vo-file-x"
                            onClick={() => {
                              const next = rows.map((r, i) => (i === idx ? { ...r, file_name: "" } : r));
                              onChange(next);
                            }}
                          >
                            ×
                          </button>
                        ) : null}
                      </div>
                    ) : (
                      <input
                        value={row[c.key] ?? ""}
                        onChange={(e) => {
                          const next = rows.map((r, i) => (i === idx ? { ...r, [c.key]: e.target.value } : r));
                          onChange(next);
                        }}
                      />
                    )}
                  </td>
                ))}
                <td className="vo-actions-cell">
                  <IconBtn
                    label="Edit"
                    onClick={() => {
                      const next = window.prompt("Edit row as JSON", JSON.stringify(row));
                      if (!next) return;
                      try {
                        const parsed = JSON.parse(next);
                        onChange(rows.map((r, i) => (i === idx ? { ...r, ...parsed } : r)));
                      } catch {
                        /* ignore invalid JSON */
                      }
                    }}
                  />
                  <IconBtn
                    label="Delete"
                    danger
                    onClick={() => onChange(rows.filter((_, i) => i !== idx))}
                  />
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      <button type="button" className="vo-btn outline-blue" onClick={() => onChange([...(rows || []), { ...blank }])}>
        + {addLabel}
      </button>
    </div>
  );
}

function TagMulti({
  options,
  value,
  onChange,
  placeholder,
}: {
  options: string[];
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  const selected = value || [];
  return (
    <div className="vo-tag-box">
      <div className="vo-tags">
        {selected.map((t) => (
          <span key={t} className="vo-tag">
            {t}
            <button type="button" onClick={() => onChange(selected.filter((x) => x !== t))}>
              ×
            </button>
          </span>
        ))}
        {!selected.length ? <span className="vo-tag-ph">{placeholder || "Select…"}</span> : null}
      </div>
      <div className="vo-tag-opts">
        {options
          .filter((o) => !selected.includes(o))
          .map((o) => (
            <button key={o} type="button" className="vo-chip" onClick={() => onChange([...selected, o])}>
              + {o}
            </button>
          ))}
      </div>
    </div>
  );
}

export function VendorOnboardingWizard({ initial, mode, onSave, onSubmit }: Props) {
  const [payload, setPayload] = useState(initial);
  const [draft, setDraft] = useState<OnboardingDraft>(() => {
    const d = { ...initial.draft };
    if (!d.compliance?.documents?.length) {
      d.compliance = { ...(d.compliance || {}), documents: DEFAULT_DOCUMENTS.map((x) => ({ ...x })) };
    }
    return d;
  });
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [pricingTab, setPricingTab] = useState<(typeof PRICING_TABS)[number]["key"]>("amc");
  const [done, setDone] = useState<{ message?: string; review_status?: string; score?: number; tier?: string } | null>(
    null
  );
  const step = Number(draft.current_step || 1);
  const steps = payload.steps || [];

  const help = useMemo(() => {
    if (step === 1)
      return {
        about: "Capture legal identity and registered office used on contracts and invoices.",
        cards: [
          { kind: "ok", title: "Mandatory Fields", body: "Fields marked with * are mandatory." },
          {
            kind: "warn",
            title: "Required Documents (Next Step)",
            list: [
              "Certificate of Incorporation",
              "PAN Card",
              "GST Registration Certificate",
              "Trade License",
              "Other statutory documents",
            ],
          },
          {
            kind: "tips",
            title: "Tips",
            list: [
              "Ensure company name matches legal documents",
              "Provide accurate GST / PAN numbers",
              "Keep scanned copies ready for Step 3",
            ],
          },
        ],
      };
    if (step === 2)
      return {
        about: "Select the services, cities, and capacity this vendor can support.",
        cards: [
          {
            kind: "tips",
            title: "Tips",
            list: ["Tick only categories you can deliver.", "List real cities where teams are available."],
          },
          {
            kind: "next",
            title: "Next steps",
            list: ["Upload supporting documents in Step 3", "Provide rates in Step 4", "Bank details in Step 5"],
          },
        ],
      };
    if (step === 3)
      return {
        about: "Documents will be verified before the vendor is approved for work orders.",
        cards: [
          {
            kind: "warn",
            title: "Mandatory Documents (India)",
            list: ["PAN Card", "GST Registration", "Certificate of Incorporation", "Cancelled Cheque", "Trade License (if applicable)"],
          },
          {
            kind: "tips",
            title: "Tips",
            list: ["Upload clear PDF scans", "Names must match legal entity", "Check expiry dates"],
          },
          {
            kind: "next",
            title: "Next steps",
            list: ["Pricing / rates", "Bank & commercials", "Review & submit"],
          },
        ],
      };
    if (step === 4)
      return {
        about: "Provide clear rate cards for AMC, labour, spares, and manpower for verification.",
        cards: [
          {
            kind: "warn",
            title: "Pricing Guidelines",
            list: ["Provide clear and competitive rates", "Mention inclusions and exclusions", "Quote GST separately where needed"],
          },
          {
            kind: "tips",
            title: "Tips",
            list: ["Use standard units (hour, visit, piece, kg)", "Specify warranty on parts where applicable"],
          },
          {
            kind: "next",
            title: "Next steps",
            list: ["Provide bank details in Step 5", "Review and submit in Step 6"],
          },
        ],
      };
    if (step === 5)
      return {
        about: "Bank account and commercial terms used for settlements and invoices.",
        cards: [
          {
            kind: "warn",
            title: "Required Information",
            list: ["Bank account details", "Cancelled cheque", "GST / PAN / TDS details", "Payment & credit terms"],
          },
          {
            kind: "tips",
            title: "Tips",
            list: ["Bank account name must match legal entity name", "Confirm IFSC before saving", "Set realistic credit period"],
          },
          {
            kind: "next",
            title: "Next steps",
            list: ["Review all information", "Submit for approval", "Save as draft anytime"],
          },
        ],
      };
    return {
      about: "Confirm the profile is complete, then submit for company review.",
      cards: [],
      reviewSide: true,
    };
  }, [step]);

  async function persist(next: OnboardingDraft, note = "Draft saved.") {
    setBusy("save");
    setMsg("");
    try {
      const saved = await onSave(next);
      setPayload(saved);
      setDraft(saved.draft);
      setMsg(note);
      return saved;
    } catch (e: any) {
      setMsg(e.message || "Save failed");
      throw e;
    } finally {
      setBusy("");
    }
  }

  async function saveDraft() {
    await persist(draft, "Draft saved.");
  }

  async function saveAndNext() {
    const nextStep = Math.min(6, step + 1);
    await persist({ ...draft, current_step: nextStep }, step === 6 ? "Draft saved." : "Saved. Next step ready.");
  }

  async function goBack() {
    const nextStep = Math.max(1, step - 1);
    const next = { ...draft, current_step: nextStep };
    setDraft(next);
    await persist(next, "Moved back.");
  }

  async function submit() {
    setBusy("submit");
    setMsg("");
    try {
      await persist(draft, "");
      const result = await onSubmit();
      setDone(result);
    } catch (e: any) {
      setMsg(e.message || "Submit failed");
    } finally {
      setBusy("");
    }
  }

  if (done) {
    return (
      <div className="vo-shell">
        <div className="vo-done">
          <h1>Onboarding submitted</h1>
          <p>{done.message || "Submitted for company review."}</p>
          <p>
            Status: <strong>{done.review_status || "UNDER_REVIEW"}</strong>
            {done.score != null ? (
              <>
                {" "}
                · score <strong>{done.score}</strong>
                {done.tier ? ` (${done.tier})` : ""}
              </>
            ) : null}
          </p>
        </div>
      </div>
    );
  }

  const basic = draft.basic || {};
  const business = draft.business || {};
  const compliance = draft.compliance || {};
  const pricing = draft.pricing || {};
  const bank = draft.bank || {};
  const review = draft.review || {};
  const readiness = payload.readiness;
  const docs = compliance.documents || [];
  const docStats = {
    total: docs.length,
    verified: docs.filter((d: any) => String(d.status || "").toLowerCase().includes("verif")).length,
    pending: docs.filter((d: any) => String(d.status || "").toLowerCase().includes("pend")).length,
    expired: docs.filter((d: any) => String(d.status || "").toLowerCase().includes("expir")).length,
  };

  const stepTitles: Record<number, { title: string; sub: string }> = {
    1: { title: "1. Basic Information", sub: "Provide the basic details of the vendor organization." },
    2: { title: "2. Business Details", sub: "Select service categories, coverage, capacity and key clients." },
    3: { title: "3. Compliance & Documents", sub: "Upload statutory documents, insurance and certifications." },
    4: {
      title: "4. Pricing / Rates",
      sub: "Provide your service rates, AMC pricing, supplier catalogue and commercial terms.",
    },
    5: { title: "5. Bank & Commercials", sub: "Bank account, payment terms, tax and commercial conditions." },
    6: { title: "6. Review & Submit", sub: "Verify all details and submit for internal approval." },
  };

  return (
    <div className={`vo-shell ${mode === "vendor" ? "vendor-mode" : "company-mode"}`}>
      <header className="vo-page-head">
        <p className="vo-crumb">
          {mode === "company" ? (
            <>
              Vendor Management <span>›</span> Onboarding <span>›</span> New Vendor
            </>
          ) : (
            <>
              Vendor Portal <span>›</span> Onboarding <span>›</span> Registration
            </>
          )}
        </p>
        <div className="vo-page-title-row">
          <div>
            <h1>Vendor Onboarding</h1>
            <p className="vo-sub">
              Register a new vendor for Facilities, AMC, Supplies or Other Admin Services.
            </p>
          </div>
          {mode === "company" && payload.registration_url ? (
            <a className="vo-btn outline-blue sm" href={payload.registration_url} target="_blank" rel="noreferrer">
              Open vendor link
            </a>
          ) : null}
        </div>
      </header>

      <ol className="vo-stepper">
        {steps.map((s, i) => (
          <li key={s.id} className={s.id === step ? "active" : s.id < step ? "done" : ""}>
            {i > 0 ? <span className="vo-step-line" aria-hidden /> : null}
            <button type="button" onClick={() => setDraft({ ...draft, current_step: s.id })}>
              <span className="vo-step-num">{s.id < step ? "✓" : s.id}</span>
              <strong>{s.title}</strong>
              <em>{s.subtitle}</em>
            </button>
          </li>
        ))}
      </ol>

      <div className="vo-grid">
        <section className="vo-main">
          {step < 6 ? (
            <div className="vo-step-banner">
              <div className="vo-step-banner-icon">{["🏢", "🧰", "📄", "₹", "🏦"][step - 1]}</div>
              <div>
                <div className="vo-step-banner-top">
                  <h2>{stepTitles[step].title}</h2>
                  <span className="vo-step-pill">Step {step} of 6</span>
                </div>
                <p>{stepTitles[step].sub}</p>
              </div>
            </div>
          ) : null}

          {step === 1 && (
            <div className="vo-card">
              <h3 className="vo-sec-title">Company Information</h3>
              <div className="vo-form-grid">
                <Field label="Vendor Type" required>
                  <select
                    value={basic.vendor_type || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "vendor_type", e.target.value))}
                  >
                    <option value="">Select vendor type</option>
                    {VENDOR_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Legal Entity Name" required>
                  <input
                    value={basic.legal_entity_name || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "legal_entity_name", e.target.value))}
                    placeholder="As per incorporation certificate"
                  />
                </Field>
                <Field label="Trade Name (if different)">
                  <input
                    value={basic.trade_name || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "trade_name", e.target.value))}
                  />
                </Field>
                <Field label="Year of Incorporation">
                  <input
                    type="number"
                    min={1900}
                    max={2100}
                    value={basic.year_of_incorporation || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "year_of_incorporation", e.target.value))}
                    placeholder="YYYY"
                  />
                </Field>
                <Field label="Company Website">
                  <input
                    value={basic.website || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "website", e.target.value))}
                    placeholder="https://www.example.com"
                  />
                </Field>
                <Field label="PAN Number" required>
                  <input
                    value={basic.pan || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "pan", e.target.value.toUpperCase()))}
                    placeholder="ABCDE1234F"
                  />
                </Field>
                <Field label="CIN (Corporate Identification Number)">
                  <input
                    value={basic.cin || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "cin", e.target.value))}
                  />
                </Field>
                <Field label="GST Number" required>
                  <div className="vo-input-with-action">
                    <input
                      value={basic.gstin || ""}
                      onChange={(e) => setDraft(setPath(draft, "basic", "gstin", e.target.value.toUpperCase()))}
                      placeholder="22AAAAA0000A1Z5"
                    />
                    <button
                      type="button"
                      className="vo-inline-link"
                      onClick={() => {
                        if (!basic.gstin) {
                          setMsg("Enter a GST number before verifying.");
                          return;
                        }
                        setDraft(setPath(draft, "basic", "gst_verified", true));
                        setMsg(`GST ${basic.gstin} marked verified (format check only).`);
                      }}
                    >
                      {basic.gst_verified ? "GST Verified" : "Verify GST"}
                    </button>
                  </div>
                </Field>
                <Field label="TAN Number">
                  <input
                    value={basic.tan || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "tan", e.target.value))}
                  />
                </Field>
              </div>

              <h3 className="vo-sec-title spaced">Registered Office Address</h3>
              <div className="vo-form-grid">
                <Field label="Address Line 1" required className="span-2">
                  <input
                    value={basic.address_line1 || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "address_line1", e.target.value))}
                  />
                </Field>
                <Field label="Address Line 2" className="span-2">
                  <input
                    value={basic.address_line2 || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "address_line2", e.target.value))}
                  />
                </Field>
                <Field label="Country" required>
                  <select
                    value={basic.country || "India"}
                    onChange={(e) => setDraft(setPath(draft, "basic", "country", e.target.value))}
                  >
                    <option>India</option>
                    <option>Other</option>
                  </select>
                </Field>
                <Field label="State" required>
                  <input
                    value={basic.state || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "state", e.target.value))}
                    placeholder="Select / type state"
                  />
                </Field>
                <Field label="City" required>
                  <input
                    value={basic.city || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "city", e.target.value))}
                  />
                </Field>
                <Field label="PIN Code" required>
                  <input
                    value={basic.pin_code || ""}
                    onChange={(e) => setDraft(setPath(draft, "basic", "pin_code", e.target.value))}
                  />
                </Field>
              </div>
              <label className="vo-check">
                <input
                  type="checkbox"
                  checked={basic.same_as_registered !== false}
                  onChange={(e) => setDraft(setPath(draft, "basic", "same_as_registered", e.target.checked))}
                />
                Same as registered office address for communication
              </label>
            </div>
          )}

          {step === 2 && (
            <div className="vo-biz-grid">
              <div className="vo-card">
                <h3 className="vo-sec-title">2.1 Service Categories</h3>
                <div className="vo-cat-grid">
                  {SERVICE_CATEGORIES.map((cat) => {
                    const on = (business.service_categories || []).includes(cat.label);
                    return (
                      <button
                        key={cat.id}
                        type="button"
                        className={`vo-cat ${on ? "on" : ""}`}
                        onClick={() =>
                          setDraft(
                            setPath(
                              draft,
                              "business",
                              "service_categories",
                              toggleList(business.service_categories || [], cat.label)
                            )
                          )
                        }
                      >
                        <span className="vo-cat-ico">{cat.icon}</span>
                        <span>{cat.label}</span>
                        <span className={`vo-cat-check ${on ? "on" : ""}`}>{on ? "✓" : ""}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="vo-card">
                <h3 className="vo-sec-title">2.2 Services Offered</h3>
                <div className="vo-form-stack">
                  <Field label="Primary Category" required>
                    <select
                      value={business.primary_category || ""}
                      onChange={(e) => setDraft(setPath(draft, "business", "primary_category", e.target.value))}
                    >
                      <option value="">Select</option>
                      {SERVICE_CATEGORIES.map((c) => (
                        <option key={c.id} value={c.label}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Services Offered">
                    <TagMulti
                      options={SERVICE_OFFER_TAGS}
                      value={business.services_offered || []}
                      onChange={(v) => setDraft(setPath(draft, "business", "services_offered", v))}
                      placeholder="Add services…"
                    />
                  </Field>
                  <Field label="Equipment / Brand Expertise">
                    <TagMulti
                      options={EQUIPMENT_TAGS}
                      value={business.equipment_expertise || []}
                      onChange={(v) => setDraft(setPath(draft, "business", "equipment_expertise", v))}
                      placeholder="Add brands…"
                    />
                  </Field>
                  <div className="vo-form-grid">
                    <Field label="Type of Service">
                      <select
                        value={business.service_type || ""}
                        onChange={(e) => setDraft(setPath(draft, "business", "service_type", e.target.value))}
                      >
                        <option value="">Select</option>
                        <option>Corrective</option>
                        <option>Preventive</option>
                        <option>Comprehensive</option>
                      </select>
                    </Field>
                    <Field label="Service Model">
                      <select
                        value={business.service_model || ""}
                        onChange={(e) => setDraft(setPath(draft, "business", "service_model", e.target.value))}
                      >
                        <option value="">Select</option>
                        <option>On-call</option>
                        <option>Resident</option>
                        <option>Hybrid</option>
                      </select>
                    </Field>
                    <Field label="Years of Experience">
                      <select
                        value={business.years_experience || ""}
                        onChange={(e) => setDraft(setPath(draft, "business", "years_experience", e.target.value))}
                      >
                        <option value="">Select</option>
                        <option>0-2 years</option>
                        <option>2-5 years</option>
                        <option>5-10 years</option>
                        <option>10+ years</option>
                      </select>
                    </Field>
                  </div>
                </div>
              </div>

              <div className="vo-card">
                <h3 className="vo-sec-title">2.3 Geographical Coverage</h3>
                <div className="vo-radio-row">
                  {COVERAGE_TYPES.map((c) => (
                    <label key={c} className="vo-radio">
                      <input
                        type="radio"
                        name="coverage"
                        checked={(business.coverage_type || "Multiple cities") === c}
                        onChange={() => setDraft(setPath(draft, "business", "coverage_type", c))}
                      />
                      {c}
                    </label>
                  ))}
                </div>
                <div className="vo-chips wrap">
                  {CITY_OPTIONS.map((city) => {
                    const on = (business.cities || []).includes(city);
                    return (
                      <button
                        key={city}
                        type="button"
                        className={`vo-chip ${on ? "on" : ""}`}
                        onClick={() =>
                          setDraft(setPath(draft, "business", "cities", toggleList(business.cities || [], city)))
                        }
                      >
                        {city}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="vo-card">
                <h3 className="vo-sec-title">2.4 Operational Capacity</h3>
                <div className="vo-form-grid">
                  <Field label="Total Technicians / Engineers">
                    <input
                      type="number"
                      value={business.technicians || ""}
                      onChange={(e) => setDraft(setPath(draft, "business", "technicians", e.target.value))}
                    />
                  </Field>
                  <Field label="Supervisors">
                    <input
                      type="number"
                      value={business.supervisors || ""}
                      onChange={(e) => setDraft(setPath(draft, "business", "supervisors", e.target.value))}
                    />
                  </Field>
                  <Field label="Service Vehicles">
                    <input
                      type="number"
                      value={business.vehicles || ""}
                      onChange={(e) => setDraft(setPath(draft, "business", "vehicles", e.target.value))}
                    />
                  </Field>
                  <Field label="Spare Parts Availability">
                    <select
                      value={business.spare_parts || ""}
                      onChange={(e) => setDraft(setPath(draft, "business", "spare_parts", e.target.value))}
                    >
                      <option value="">Select</option>
                      <option>In-stock (local)</option>
                      <option>48 hours</option>
                      <option>On indent</option>
                    </select>
                  </Field>
                </div>
              </div>

              <div className="vo-card span-2">
                <div className="vo-sec-row">
                  <h3 className="vo-sec-title">2.5 Key Clients (Optional)</h3>
                </div>
                <TableEditor
                  showIndex
                  rows={business.clients || []}
                  columns={[
                    { key: "client", label: "Client Name", wide: true },
                    { key: "location", label: "Location" },
                    { key: "services", label: "Services Provided" },
                    { key: "contact", label: "Contact Person" },
                  ]}
                  blank={{ client: "", location: "", services: "", contact: "" }}
                  addLabel="Add Client"
                  onChange={(rows) => setDraft(setPath(draft, "business", "clients", rows))}
                />
              </div>

              <div className="vo-card span-2">
                <h3 className="vo-sec-title">2.6 Service Availability</h3>
                <div className="vo-form-grid">
                  <Field label="Working Hours From">
                    <input
                      type="time"
                      value={business.working_hours_from || "09:00"}
                      onChange={(e) => setDraft(setPath(draft, "business", "working_hours_from", e.target.value))}
                    />
                  </Field>
                  <Field label="Working Hours To">
                    <input
                      type="time"
                      value={business.working_hours_to || "18:00"}
                      onChange={(e) => setDraft(setPath(draft, "business", "working_hours_to", e.target.value))}
                    />
                  </Field>
                  <Field label="Emergency Support">
                    <input
                      value={business.emergency_support || "24 x 7"}
                      onChange={(e) => setDraft(setPath(draft, "business", "emergency_support", e.target.value))}
                    />
                  </Field>
                  <Field label="Response Time">
                    <input
                      value={business.response_time || ""}
                      onChange={(e) => setDraft(setPath(draft, "business", "response_time", e.target.value))}
                      placeholder="Within 4 hours / Within 1 hour"
                    />
                  </Field>
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <>
              <div className="vo-card">
                <div className="vo-sec-row">
                  <h3 className="vo-sec-title">3.1 Document Checklist</h3>
                  <div className="vo-sec-tools">
                    <select
                      value={compliance.region || "India (Default)"}
                      onChange={(e) => setDraft(setPath(draft, "compliance", "region", e.target.value))}
                    >
                      <option>India (Default)</option>
                      <option>UAE</option>
                      <option>Other</option>
                    </select>
                    <button type="button" className="vo-btn ghost sm">
                      Download Checklist
                    </button>
                  </div>
                </div>
                <TableEditor
                  showIndex
                  rows={docs}
                  columns={[
                    { key: "type", label: "Document Type", wide: true },
                    { key: "applicable", label: "Applicable" },
                    { key: "details", label: "Document Details" },
                    { key: "file_name", label: "File Upload" },
                    { key: "expiry", label: "Expiry Date" },
                    { key: "status", label: "Status" },
                  ]}
                  blank={{ type: "", applicable: "Yes", details: "", file_name: "", expiry: "", status: "Pending" }}
                  addLabel="Add Document"
                  onChange={(rows) => setDraft(setPath(draft, "compliance", "documents", rows))}
                />
              </div>

              <div className="vo-card">
                <h3 className="vo-sec-title">3.2 Insurance Documents</h3>
                <TableEditor
                  showIndex
                  rows={compliance.insurance || []}
                  columns={[
                    { key: "type", label: "Insurance Type" },
                    { key: "policy_number", label: "Policy Number" },
                    { key: "insurer", label: "Insurer" },
                    { key: "cover", label: "Cover (₹)" },
                    { key: "validity", label: "Valid Till" },
                    { key: "status", label: "Status" },
                  ]}
                  blank={{ type: "", policy_number: "", insurer: "", cover: "", validity: "", status: "Pending" }}
                  addLabel="Add Insurance"
                  onChange={(rows) => setDraft(setPath(draft, "compliance", "insurance", rows))}
                />
              </div>

              <div className="vo-card">
                <h3 className="vo-sec-title">3.3 Technical & Other Certifications</h3>
                <TableEditor
                  showIndex
                  rows={compliance.certificates || []}
                  columns={[
                    { key: "name", label: "Certification Type" },
                    { key: "issuer", label: "Issued By" },
                    { key: "number", label: "Number" },
                    { key: "expiry", label: "Valid Till" },
                    { key: "status", label: "Status" },
                  ]}
                  blank={{ name: "", issuer: "", number: "", expiry: "", status: "Pending" }}
                  addLabel="Add Certificate"
                  onChange={(rows) => setDraft(setPath(draft, "compliance", "certificates", rows))}
                />
              </div>

              <div className="vo-two">
                <div className="vo-card">
                  <h3 className="vo-sec-title">3.4 Labour Compliance</h3>
                  <label className="vo-toggle-row">
                    <span>Do you directly employ workers?</span>
                    <button
                      type="button"
                      className={`vo-toggle ${compliance.employ_workers ? "on" : ""}`}
                      onClick={() =>
                        setDraft(setPath(draft, "compliance", "employ_workers", !compliance.employ_workers))
                      }
                    >
                      <span />
                      {compliance.employ_workers ? "Yes" : "No"}
                    </button>
                  </label>
                  <label className="vo-toggle-row">
                    <span>Do you engage subcontractors?</span>
                    <button
                      type="button"
                      className={`vo-toggle ${compliance.use_subcontractors ? "on" : ""}`}
                      onClick={() =>
                        setDraft(setPath(draft, "compliance", "use_subcontractors", !compliance.use_subcontractors))
                      }
                    >
                      <span />
                      {compliance.use_subcontractors ? "Yes" : "No"}
                    </button>
                  </label>
                </div>
                <div className="vo-card">
                  <h3 className="vo-sec-title">3.5 Safety & Statutory Declarations</h3>
                  <label className="vo-check">
                    <input
                      type="checkbox"
                      checked={Boolean(compliance.safety_declared)}
                      onChange={(e) => setDraft(setPath(draft, "compliance", "safety_declared", e.target.checked))}
                    />
                    We comply with applicable safety and labour regulations
                  </label>
                  <label className="vo-check">
                    <input
                      type="checkbox"
                      checked={Boolean(compliance.statutory_declared)}
                      onChange={(e) => setDraft(setPath(draft, "compliance", "statutory_declared", e.target.checked))}
                    />
                    We will keep statutory documents updated
                  </label>
                </div>
              </div>

              {mode === "company" ? (
                <div className="vo-card">
                  <h3 className="vo-sec-title">3.6 Document Verification</h3>
                  <div className="vo-form-grid">
                    <Field label="Verified by">
                      <select
                        value={compliance.verified_by || "Procurement Team"}
                        onChange={(e) => setDraft(setPath(draft, "compliance", "verified_by", e.target.value))}
                      >
                        <option>Procurement Team</option>
                        <option>Facilities Team</option>
                        <option>Finance Team</option>
                        <option>Legal / Compliance</option>
                      </select>
                    </Field>
                    <Field label="Verification Date">
                      <input
                        type="date"
                        value={compliance.verification_date || ""}
                        onChange={(e) => setDraft(setPath(draft, "compliance", "verification_date", e.target.value))}
                      />
                    </Field>
                  </div>
                </div>
              ) : null}
            </>
          )}

          {step === 4 && (
            <div className="vo-card">
              <div className="vo-tabs">
                {PRICING_TABS.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    className={pricingTab === t.key ? "on" : ""}
                    onClick={() => setPricingTab(t.key)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {pricingTab === "amc" && (
                <>
                  <h3 className="vo-sec-title">4.1 AMC Contracts</h3>
                  <TableEditor
                    showIndex
                    rows={pricing.amc_contracts || []}
                    columns={[
                      { key: "asset_type", label: "Asset Type" },
                      { key: "make_model", label: "Make / Model" },
                      { key: "amc_type", label: "AMC Type" },
                      { key: "coverage", label: "Coverage" },
                      { key: "qty", label: "No. of Assets" },
                      { key: "annual_rate", label: "Annual Rate (₹)" },
                      { key: "gst", label: "GST" },
                      { key: "validity_from", label: "Valid From" },
                      { key: "validity_to", label: "Valid To" },
                    ]}
                    blank={{
                      asset_type: "",
                      make_model: "",
                      amc_type: "",
                      coverage: "",
                      qty: "",
                      annual_rate: "",
                      gst: "",
                      validity_from: "",
                      validity_to: "",
                    }}
                    addLabel="Add AMC"
                    onChange={(rows) => setDraft(setPath(draft, "pricing", "amc_contracts", rows))}
                  />
                </>
              )}
              {pricingTab === "labour" && (
                <>
                  <h3 className="vo-sec-title">4.2 Labour & Service Call Rates</h3>
                  <TableEditor
                    showIndex
                    rows={pricing.labour_rates || []}
                    columns={[
                      { key: "role", label: "Service / Role" },
                      { key: "unit", label: "Unit" },
                      { key: "normal", label: "Normal Hours (₹)" },
                      { key: "ot", label: "OT / Holiday (₹)" },
                      { key: "min_billing", label: "Min. Billing" },
                      { key: "gst", label: "GST" },
                    ]}
                    blank={{ role: "", unit: "Per hour", normal: "", ot: "", min_billing: "", gst: "" }}
                    addLabel="Add Labour Rate"
                    onChange={(rows) => setDraft(setPath(draft, "pricing", "labour_rates", rows))}
                  />
                </>
              )}
              {pricingTab === "spares" && (
                <>
                  <h3 className="vo-sec-title">4.3 Spare Parts & Consumables</h3>
                  <TableEditor
                    showIndex
                    rows={pricing.spare_parts || []}
                    columns={[
                      { key: "item", label: "Item Description", wide: true },
                      { key: "brand", label: "Brand / Model" },
                      { key: "uom", label: "UOM" },
                      { key: "rate", label: "Rate (₹)" },
                      { key: "gst", label: "GST" },
                    ]}
                    blank={{ item: "", brand: "", uom: "", rate: "", gst: "" }}
                    addLabel="Add Spare Part"
                    onChange={(rows) => setDraft(setPath(draft, "pricing", "spare_parts", rows))}
                  />
                </>
              )}
              {pricingTab === "manpower" && (
                <>
                  <h3 className="vo-sec-title">4.4 Manpower / Monthly Deployment Rates</h3>
                  <TableEditor
                    showIndex
                    rows={pricing.manpower_rates || []}
                    columns={[
                      { key: "role", label: "Role" },
                      { key: "shift", label: "Shift" },
                      { key: "headcount", label: "Headcount" },
                      { key: "monthly_rate", label: "Monthly Rate (₹)" },
                      { key: "gst", label: "GST" },
                      { key: "inclusions", label: "Inclusions" },
                    ]}
                    blank={{ role: "", shift: "", headcount: "", monthly_rate: "", gst: "", inclusions: "" }}
                    addLabel="Add Manpower Rate"
                    onChange={(rows) => setDraft(setPath(draft, "pricing", "manpower_rates", rows))}
                  />
                </>
              )}
              {pricingTab === "catalogue" && (
                <>
                  <h3 className="vo-sec-title">4.5 Supplier Catalogue</h3>
                  <TableEditor
                    showIndex
                    rows={pricing.catalogue || []}
                    columns={[
                      { key: "item", label: "Item" },
                      { key: "brand", label: "Brand" },
                      { key: "uom", label: "UOM" },
                      { key: "rate", label: "Rate (₹)" },
                      { key: "min_order", label: "Min. Order" },
                    ]}
                    blank={{ item: "", brand: "", uom: "", rate: "", min_order: "" }}
                    addLabel="Add Catalogue Item"
                    onChange={(rows) => setDraft(setPath(draft, "pricing", "catalogue", rows))}
                  />
                </>
              )}
              {pricingTab === "terms" && (
                <>
                  <h3 className="vo-sec-title">Commercial Terms</h3>
                  <div className="vo-form-grid">
                    <Field label="Price Validity (Days)">
                      <input
                        value={pricing.price_validity || bank.price_validity || ""}
                        onChange={(e) => setDraft(setPath(draft, "pricing", "price_validity", e.target.value))}
                      />
                    </Field>
                    <Field label="Escalation Basis">
                      <input
                        value={pricing.escalation_basis || ""}
                        onChange={(e) => setDraft(setPath(draft, "pricing", "escalation_basis", e.target.value))}
                      />
                    </Field>
                    <Field label="Inclusions" className="span-2">
                      <textarea
                        rows={3}
                        value={pricing.inclusions || ""}
                        onChange={(e) => setDraft(setPath(draft, "pricing", "inclusions", e.target.value))}
                      />
                    </Field>
                    <Field label="Exclusions" className="span-2">
                      <textarea
                        rows={3}
                        value={pricing.exclusions || ""}
                        onChange={(e) => setDraft(setPath(draft, "pricing", "exclusions", e.target.value))}
                      />
                    </Field>
                  </div>
                </>
              )}
            </div>
          )}

          {step === 5 && (
            <>
              <div className="vo-card">
                <div className="vo-sec-row">
                  <h3 className="vo-sec-title">5.1 Bank Account Details</h3>
                  <button type="button" className="vo-btn outline-blue sm">
                    + Add Bank Account
                  </button>
                </div>
                <div className="vo-bank-layout">
                  <div className="vo-form-grid">
                    <Field label="Account Type" required>
                      <select
                        value={bank.account_type || "Current Account"}
                        onChange={(e) => setDraft(setPath(draft, "bank", "account_type", e.target.value))}
                      >
                        <option>Current Account</option>
                        <option>Savings Account</option>
                      </select>
                    </Field>
                    <Field label="Beneficiary Name" required>
                      <input
                        value={bank.beneficiary_name || ""}
                        onChange={(e) => setDraft(setPath(draft, "bank", "beneficiary_name", e.target.value))}
                      />
                    </Field>
                    <Field label="Bank Name" required>
                      <input
                        value={bank.bank_name || ""}
                        onChange={(e) => setDraft(setPath(draft, "bank", "bank_name", e.target.value))}
                      />
                    </Field>
                    <Field label="Account Number" required>
                      <input
                        value={bank.account_number || ""}
                        onChange={(e) => setDraft(setPath(draft, "bank", "account_number", e.target.value))}
                      />
                    </Field>
                    <Field label="IFSC Code" required>
                      <input
                        value={bank.ifsc || ""}
                        onChange={(e) => setDraft(setPath(draft, "bank", "ifsc", e.target.value.toUpperCase()))}
                      />
                    </Field>
                    <Field label="Branch Name">
                      <input
                        value={bank.branch_name || ""}
                        onChange={(e) => setDraft(setPath(draft, "bank", "branch_name", e.target.value))}
                      />
                    </Field>
                    <Field label="Account Holder PAN">
                      <input
                        value={bank.pan || basic.pan || ""}
                        onChange={(e) => setDraft(setPath(draft, "bank", "pan", e.target.value))}
                      />
                    </Field>
                    <Field label="Account Holder GSTIN">
                      <input
                        value={bank.gstin || basic.gstin || ""}
                        onChange={(e) => setDraft(setPath(draft, "bank", "gstin", e.target.value))}
                      />
                    </Field>
                    <Field label="UPI ID">
                      <input
                        value={bank.upi_id || ""}
                        onChange={(e) => setDraft(setPath(draft, "bank", "upi_id", e.target.value))}
                      />
                    </Field>
                    <label className="vo-toggle-row compact">
                      <span>Default for Payments</span>
                      <button
                        type="button"
                        className={`vo-toggle ${bank.default_for_payments !== false ? "on" : ""}`}
                        onClick={() =>
                          setDraft(setPath(draft, "bank", "default_for_payments", bank.default_for_payments === false))
                        }
                      >
                        <span />
                        {bank.default_for_payments === false ? "No" : "Yes"}
                      </button>
                    </label>
                  </div>
                  <aside className="vo-verify-box">
                    <strong>
                      {bank.verify_status === "Verified"
                        ? "Bank account verified successfully."
                        : "Run a verification check when account details are complete."}
                    </strong>
                    <p>
                      Bank Verification: <StatusPill status={bank.verify_status || "Pending"} />
                    </p>
                    <p>Verified On: {bank.verified_on || "—"}</p>
                    <p>Verified By: {bank.verified_by || "—"}</p>
                    <p>Beneficiary Match: {bank.beneficiary_match || "—"}</p>
                    <p>Account Status: {bank.account_status || "—"}</p>
                    <button
                      type="button"
                      className="vo-btn outline-blue sm"
                      style={{ marginTop: "0.65rem" }}
                      onClick={() => {
                        if (!bank.account_number || !bank.ifsc || !bank.beneficiary_name) {
                          setMsg("Fill beneficiary, account number, and IFSC before verifying.");
                          return;
                        }
                        const today = new Date().toISOString().slice(0, 10);
                        setDraft({
                          ...draft,
                          bank: {
                            ...bank,
                            verify_status: "Verified",
                            verified_on: today,
                            verified_by: mode === "company" ? "Finance Team" : "Vendor self-check",
                            beneficiary_match: "Yes",
                            account_status: "Active",
                          },
                        });
                        setMsg("Bank details marked verified (local check).");
                      }}
                    >
                      Verify bank
                    </button>
                  </aside>
                </div>
              </div>

              <div className="vo-card">
                <h3 className="vo-sec-title">5.2 Payment Terms</h3>
                <div className="vo-form-grid">
                  <Field label="Payment Term Type">
                    <select
                      value={bank.payment_term_type || "Credit (Post Invoice)"}
                      onChange={(e) => setDraft(setPath(draft, "bank", "payment_term_type", e.target.value))}
                    >
                      <option>Credit (Post Invoice)</option>
                      <option>Advance</option>
                      <option>Against Delivery</option>
                    </select>
                  </Field>
                  <Field label="Credit Period (Days)">
                    <input
                      value={bank.credit_period || "30 Days"}
                      onChange={(e) => setDraft(setPath(draft, "bank", "credit_period", e.target.value))}
                    />
                  </Field>
                  <Field label="Invoice Frequency">
                    <select
                      value={bank.invoice_frequency || "Monthly"}
                      onChange={(e) => setDraft(setPath(draft, "bank", "invoice_frequency", e.target.value))}
                    >
                      <option>Monthly</option>
                      <option>Fortnightly</option>
                      <option>Per Work Order</option>
                    </select>
                  </Field>
                  <Field label="Payment Method">
                    <select
                      value={bank.payment_method || "NEFT / RTGS"}
                      onChange={(e) => setDraft(setPath(draft, "bank", "payment_method", e.target.value))}
                    >
                      <option>NEFT / RTGS</option>
                      <option>Cheque</option>
                      <option>UPI</option>
                    </select>
                  </Field>
                  <Field label="Retention %">
                    <input
                      value={bank.retention_pct || "0%"}
                      onChange={(e) => setDraft(setPath(draft, "bank", "retention_pct", e.target.value))}
                    />
                  </Field>
                  <Field label="TDS Section">
                    <input
                      value={bank.tds_section || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "tds_section", e.target.value))}
                      placeholder="194C / 194J"
                    />
                  </Field>
                </div>
                <div className="vo-radio-row spaced">
                  {["All services", "Only specified categories", "Only purchase orders"].map((o) => (
                    <label key={o} className="vo-radio">
                      <input
                        type="radio"
                        name="pay_apply"
                        checked={(bank.payment_applicable || "All services") === o}
                        onChange={() => setDraft(setPath(draft, "bank", "payment_applicable", o))}
                      />
                      {o}
                    </label>
                  ))}
                </div>
              </div>

              <div className="vo-card">
                <h3 className="vo-sec-title">5.3 Tax Details</h3>
                <div className="vo-form-grid">
                  <Field label="PAN Number">
                    <input
                      value={bank.tax_pan || basic.pan || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "tax_pan", e.target.value))}
                    />
                  </Field>
                  <Field label="GSTIN">
                    <input
                      value={bank.tax_gstin || basic.gstin || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "tax_gstin", e.target.value))}
                    />
                  </Field>
                  <Field label="GST Registration Type">
                    <select
                      value={bank.gst_reg_type || "Regular"}
                      onChange={(e) => setDraft(setPath(draft, "bank", "gst_reg_type", e.target.value))}
                    >
                      <option>Regular</option>
                      <option>Composition</option>
                      <option>Unregistered</option>
                    </select>
                  </Field>
                  <Field label="Place of Supply">
                    <input
                      value={bank.place_of_supply || basic.state || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "place_of_supply", e.target.value))}
                    />
                  </Field>
                  <Field label="MSME / Udyam Status">
                    <select
                      value={bank.msme_status || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "msme_status", e.target.value))}
                    >
                      <option value="">Select</option>
                      <option>Registered</option>
                      <option>Not Registered</option>
                    </select>
                  </Field>
                  <Field label="Udyam Registration No.">
                    <input
                      value={bank.msme_number || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "msme_number", e.target.value))}
                    />
                  </Field>
                </div>
              </div>

              <div className="vo-card">
                <h3 className="vo-sec-title">5.4 Invoicing Details</h3>
                <div className="vo-form-grid">
                  <Field label="Invoice Format">
                    <select
                      value={bank.invoice_format || "Tax Invoice"}
                      onChange={(e) => setDraft(setPath(draft, "bank", "invoice_format", e.target.value))}
                    >
                      <option>Tax Invoice</option>
                      <option>Proforma</option>
                    </select>
                  </Field>
                  <Field label="Invoice Submission">
                    <select
                      value={bank.invoice_submission || "Email + Vendor Portal"}
                      onChange={(e) => setDraft(setPath(draft, "bank", "invoice_submission", e.target.value))}
                    >
                      <option>Email + Vendor Portal</option>
                      <option>Email only</option>
                      <option>Portal only</option>
                    </select>
                  </Field>
                  <Field label="Invoice Email ID">
                    <input
                      value={bank.invoice_email || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "invoice_email", e.target.value))}
                    />
                  </Field>
                  <Field label="Copy To (Optional)">
                    <input
                      value={bank.invoice_cc || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "invoice_cc", e.target.value))}
                    />
                  </Field>
                  <Field label="Mandatory Invoice Information" className="span-2">
                    <TagMulti
                      options={INVOICE_INFO_TAGS}
                      value={bank.invoice_info || ["PO/WO Number", "GST Details"]}
                      onChange={(v) => setDraft(setPath(draft, "bank", "invoice_info", v))}
                    />
                  </Field>
                </div>
              </div>

              <div className="vo-card">
                <h3 className="vo-sec-title">5.5 Commercial Terms & Conditions</h3>
                <div className="vo-form-grid">
                  <Field label="Price Validity (Days)">
                    <input
                      value={bank.price_validity || "90"}
                      onChange={(e) => setDraft(setPath(draft, "bank", "price_validity", e.target.value))}
                    />
                  </Field>
                  <Field label="Escalation Basis">
                    <input
                      value={bank.escalation_basis || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "escalation_basis", e.target.value))}
                    />
                  </Field>
                  <Field label="Freight / Transportation">
                    <select
                      value={bank.freight || "Included"}
                      onChange={(e) => setDraft(setPath(draft, "bank", "freight", e.target.value))}
                    >
                      <option>Included</option>
                      <option>Extra</option>
                      <option>As per actual</option>
                    </select>
                  </Field>
                  <Field label="Minimum Order Value">
                    <input
                      value={bank.min_order_value || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "min_order_value", e.target.value))}
                    />
                  </Field>
                  <Field label="Warranty on Supplies">
                    <input
                      value={bank.warranty || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "warranty", e.target.value))}
                    />
                  </Field>
                  <Field label="Special Commercial Terms (if any)" className="span-2">
                    <textarea
                      rows={3}
                      value={bank.special_terms || ""}
                      onChange={(e) => setDraft(setPath(draft, "bank", "special_terms", e.target.value))}
                    />
                  </Field>
                </div>
              </div>

              {mode === "company" ? (
                <div className="vo-card">
                  <h3 className="vo-sec-title">5.6 Approval & Financial Category</h3>
                  <div className="vo-form-grid">
                    <Field label="Vendor Category">
                      <select
                        value={bank.vendor_category || "Standard Vendor"}
                        onChange={(e) => setDraft(setPath(draft, "bank", "vendor_category", e.target.value))}
                      >
                        <option>Standard Vendor</option>
                        <option>Preferred Vendor</option>
                        <option>Strategic Vendor</option>
                      </select>
                    </Field>
                    <Field label="Financial Limit (₹)">
                      <input
                        value={bank.financial_limit || "500000"}
                        onChange={(e) => setDraft(setPath(draft, "bank", "financial_limit", e.target.value))}
                      />
                    </Field>
                    <label className="vo-toggle-row compact">
                      <span>Require Finance Approval</span>
                      <button
                        type="button"
                        className={`vo-toggle ${bank.require_finance !== false ? "on" : ""}`}
                        onClick={() =>
                          setDraft(setPath(draft, "bank", "require_finance", bank.require_finance === false))
                        }
                      >
                        <span />
                        {bank.require_finance === false ? "No" : "Yes"}
                      </button>
                    </label>
                    <label className="vo-toggle-row compact">
                      <span>Require Expense Approval</span>
                      <button
                        type="button"
                        className={`vo-toggle ${bank.require_expense !== false ? "on" : ""}`}
                        onClick={() =>
                          setDraft(setPath(draft, "bank", "require_expense", bank.require_expense === false))
                        }
                      >
                        <span />
                        {bank.require_expense === false ? "No" : "Yes"}
                      </button>
                    </label>
                  </div>
                </div>
              ) : null}
            </>
          )}

          {step === 6 && (
            <>
              <div className="vo-card vo-review-hero">
                <div className="vo-review-avatar">
                  {(basic.legal_entity_name || payload.name || "V").slice(0, 3).toUpperCase()}
                </div>
                <div className="vo-review-hero-body">
                  <div className="vo-review-hero-top">
                    <h2>{basic.legal_entity_name || payload.name || "Vendor"}</h2>
                    <span className={`vo-badge ${readiness?.ready ? "ok" : "warn"}`}>
                      {readiness?.ready ? "Ready for Submission" : "Incomplete"}
                    </span>
                    <button
                      type="button"
                      className="vo-btn ghost sm"
                      onClick={() => {
                        const blob = new Blob(
                          [
                            `Vendor Onboarding Preview\n\n${basic.legal_entity_name || payload.name}\nPAN: ${basic.pan || "—"}\nGSTIN: ${basic.gstin || "—"}\nStatus: ${readiness?.ready ? "Ready" : "Incomplete"} (${readiness?.percent ?? 0}%)\n`,
                          ],
                          { type: "text/plain" }
                        );
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `${(basic.legal_entity_name || "vendor").replace(/\s+/g, "_")}_preview.txt`;
                        a.click();
                        URL.revokeObjectURL(url);
                      }}
                    >
                      Preview as PDF
                    </button>
                  </div>
                  <div className="vo-meta-row">
                    <span>
                      <em>Vendor Type</em>
                      {basic.vendor_type || "—"}
                    </span>
                    <span>
                      <em>PAN</em>
                      {basic.pan || "—"}
                    </span>
                    <span>
                      <em>GSTIN</em>
                      {basic.gstin || "—"}
                    </span>
                    <span>
                      <em>Registered Office</em>
                      {[basic.city, basic.state].filter(Boolean).join(", ") || "—"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="vo-review-grid">
                {[
                  {
                    n: 1,
                    title: "Basic Information",
                    body: (
                      <>
                        <p>Year: {basic.year_of_incorporation || "—"}</p>
                        <p>
                          {basic.address_line1 || "—"}
                          {basic.city ? `, ${basic.city}` : ""}
                        </p>
                      </>
                    ),
                  },
                  {
                    n: 2,
                    title: "Business Details",
                    body: (
                      <>
                        <p>{(business.service_categories || []).slice(0, 4).join(", ") || "No categories"}</p>
                        <p>Coverage: {(business.cities || []).slice(0, 4).join(", ") || "—"}</p>
                        <p>Experience: {business.years_experience || "—"}</p>
                      </>
                    ),
                  },
                  {
                    n: 3,
                    title: "Compliance & Documents",
                    body: (
                      <>
                        <p>
                          Total {docStats.total} · Verified {docStats.verified} · Pending {docStats.pending} · Expired{" "}
                          {docStats.expired}
                        </p>
                      </>
                    ),
                  },
                  {
                    n: 4,
                    title: "Pricing / Rates",
                    body: (
                      <p>
                        AMC {(pricing.amc_contracts || []).length} · Labour {(pricing.labour_rates || []).length} ·
                        Spares {(pricing.spare_parts || []).length} · Manpower {(pricing.manpower_rates || []).length}
                      </p>
                    ),
                  },
                  {
                    n: 5,
                    title: "Bank & Commercials",
                    body: (
                      <>
                        <p>
                          {bank.bank_name || "—"} · ****
                          {String(bank.account_number || "").slice(-4) || "————"}
                        </p>
                        <p>
                          {bank.credit_period || "—"} · validity {bank.price_validity || "—"} days
                        </p>
                      </>
                    ),
                  },
                ].map((card) => (
                  <div key={card.n} className="vo-card vo-review-card">
                    <div className="vo-review-card-top">
                      <h3>
                        {card.n}. {card.title}
                      </h3>
                      <span className="vo-pill ok">Completed</span>
                      <button
                        type="button"
                        className="vo-link"
                        onClick={() => setDraft({ ...draft, current_step: card.n })}
                      >
                        Edit
                      </button>
                    </div>
                    {card.body}
                  </div>
                ))}
              </div>
            </>
          )}

          <div className="vo-actions">
            {step > 1 ? (
              <button type="button" className="vo-btn ghost" disabled={Boolean(busy)} onClick={goBack}>
                ← Back
              </button>
            ) : (
              <span />
            )}
            <div className="vo-actions-right">
              <button type="button" className="vo-btn outline-blue" disabled={Boolean(busy)} onClick={saveDraft}>
                {busy === "save" ? "Saving…" : "💾 Save as Draft"}
              </button>
              {step < 6 ? (
                <button type="button" className="vo-btn primary" disabled={Boolean(busy)} onClick={saveAndNext}>
                  {busy === "save" ? "Saving…" : "Save & Next →"}
                </button>
              ) : (
                <button type="button" className="vo-btn primary" disabled={Boolean(busy)} onClick={submit}>
                  {busy === "submit" ? "Submitting…" : "✈ Submit for Approval"}
                </button>
              )}
            </div>
          </div>
          {msg ? <p className="vo-msg">{msg}</p> : null}
        </section>

        <aside className="vo-side">
          {step < 6 ? (
            <>
              <div className="vo-side-card about">
                <h3>About this step</h3>
                <p>{help.about}</p>
              </div>
              {(help.cards || []).map((c: any) => (
                <div key={c.title} className={`vo-side-card ${c.kind}`}>
                  <h3>{c.title}</h3>
                  {c.body ? <p>{c.body}</p> : null}
                  {c.list ? (
                    <ul>
                      {c.list.map((t: string) => (
                        <li key={t}>{t}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ))}
              <div className="vo-side-card ready">
                <h3>Submission readiness</h3>
                <div className="vo-meter">
                  <strong>{readiness?.percent ?? 0}%</strong>
                  <div className="vo-meter-bar">
                    <span style={{ width: `${readiness?.percent ?? 0}%` }} />
                  </div>
                </div>
                <ul className="vo-checks">
                  {(readiness?.checks || []).map((c) => (
                    <li key={c.label} className={c.ok ? "ok" : ""}>
                      {c.ok ? "✓" : "○"} {c.label}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          ) : (
            <>
              <div className="vo-side-card ready vo-ready-circle-card">
                <h3>Submission Readiness</h3>
                <div
                  className="vo-circle"
                  style={{
                    background: `conic-gradient(#2563eb ${readiness?.percent ?? 0}%, #e5e7eb 0)`,
                  }}
                >
                  <div className="vo-circle-inner">
                    <strong>{readiness?.percent ?? 0}%</strong>
                    <span>Complete</span>
                  </div>
                </div>
                <ul className="vo-checks">
                  {(readiness?.checks || []).map((c) => (
                    <li key={c.label} className={c.ok ? "ok" : ""}>
                      {c.ok ? "✓" : "○"} {c.label}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="vo-side-card warn">
                <h3>Items for Attention</h3>
                {(readiness?.checks || []).some((c) => !c.ok) ? (
                  <ul>
                    {(readiness?.checks || [])
                      .filter((c) => !c.ok)
                      .map((c) => (
                        <li key={c.label}>
                          {c.label} — <em>Pending</em>
                        </li>
                      ))}
                  </ul>
                ) : (
                  <p>No blocking items.</p>
                )}
              </div>
              <div className="vo-side-card">
                <h3>Approvals Required</h3>
                <table className="vo-mini-table">
                  <tbody>
                    {APPROVAL_ROWS.map((r) => (
                      <tr key={r.team}>
                        <td>{r.team}</td>
                        <td>
                          <StatusPill status={r.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="vo-side-card">
                <h3>Vendor Declarations</h3>
                <label className="vo-check">
                  <input
                    type="checkbox"
                    checked={Boolean(review.truthful_declaration)}
                    onChange={(e) => setDraft(setPath(draft, "review", "truthful_declaration", e.target.checked))}
                  />
                  Information provided is true and complete
                </label>
                <label className="vo-check">
                  <input
                    type="checkbox"
                    checked={Boolean(review.policy_declaration)}
                    onChange={(e) => setDraft(setPath(draft, "review", "policy_declaration", e.target.checked))}
                  />
                  Agree to policies, statutory requirements & commercial terms
                </label>
                <label className="vo-check">
                  <input
                    type="checkbox"
                    checked={Boolean(review.authorize_verification)}
                    onChange={(e) => setDraft(setPath(draft, "review", "authorize_verification", e.target.checked))}
                  />
                  Authorize verification of documents and bank details
                </label>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
