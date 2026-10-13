"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

export default function VendorRegisterPage() {
  const params = useParams();
  const token = String(params?.token || "");
  const [form, setForm] = useState<any>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [payload, setPayload] = useState({
    legal_name: "",
    gstin: "",
    pan: "",
    contact_name: "",
    contact_phone: "",
    registered_address: "",
    coverage_states: "",
    coverage_cities: "",
    years_in_business: "",
    employee_count: "",
    annual_turnover: "",
    gst_certificate: true,
    pan_card: true,
  });

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/public/vendors/register/${token}`)
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Invalid link");
        return res.json();
      })
      .then((data) => {
        setForm(data);
        setPayload((p) => ({
          ...p,
          legal_name: data.existing?.legal_name || "",
          gstin: data.existing?.gstin || "",
          pan: data.existing?.pan || "",
          contact_name: data.contact_name || "",
          coverage_cities: (data.existing?.coverage_cities || []).join(", "),
          coverage_states: (data.existing?.coverage_states || []).join(", "),
        }));
      })
      .catch((e) => setError(e.message || "Could not load registration"));
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = {
        legal_name: payload.legal_name || form?.name,
        gstin: payload.gstin,
        pan: payload.pan,
        contact_name: payload.contact_name,
        contact_phone: payload.contact_phone,
        registered_address: payload.registered_address,
        coverage_states: payload.coverage_states.split(",").map((s) => s.trim()).filter(Boolean),
        coverage_cities: payload.coverage_cities.split(",").map((s) => s.trim()).filter(Boolean),
        documents: {
          gst_certificate: payload.gst_certificate,
          pan_card: payload.pan_card,
        },
        compliance: {
          years_in_business: payload.years_in_business,
          employee_count: payload.employee_count,
          annual_turnover: payload.annual_turnover,
        },
        financial: {
          annual_turnover: payload.annual_turnover,
          gst_compliant: true,
        },
        manpower: {
          permanent_employees: Number(payload.employee_count) || 0,
        },
        coverage_rows: payload.coverage_cities
          .split(",")
          .map((c) => c.trim())
          .filter(Boolean)
          .map((city) => ({ city, state: payload.coverage_states.split(",")[0]?.trim() || null, team_count: 1 })),
      };
      const res = await fetch(`${API_BASE}/public/vendors/register/${token}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Submit failed");
      setDone(data);
    } catch (err: any) {
      setError(err.message || "Submit failed");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <main style={{ maxWidth: 640, margin: "3rem auto", padding: "0 1rem", fontFamily: "system-ui,sans-serif" }}>
        <h1>Registration submitted</h1>
        <p>{done.message}</p>
        <p>
          Status: <strong>{done.review_status}</strong>
          {done.score != null ? (
            <>
              {" "}
              · provisional score <strong>{done.score}</strong> ({done.tier})
            </>
          ) : null}
        </p>
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 640, margin: "3rem auto", padding: "0 1rem", fontFamily: "system-ui,sans-serif" }}>
      <h1>Vendor registration</h1>
      {error ? <p style={{ color: "#b00020" }}>{error}</p> : null}
      {!form && !error ? <p>Loading…</p> : null}
      {form ? (
        <form onSubmit={submit} style={{ display: "grid", gap: "0.75rem" }}>
          <p>
            Completing registration for <strong>{form.name}</strong> ({form.category}) — {form.contact_email}
          </p>
          <label>
            Legal name
            <input style={{ width: "100%" }} value={payload.legal_name} onChange={(e) => setPayload({ ...payload, legal_name: e.target.value })} required />
          </label>
          <label>
            Contact person
            <input style={{ width: "100%" }} value={payload.contact_name} onChange={(e) => setPayload({ ...payload, contact_name: e.target.value })} required />
          </label>
          <label>
            Phone
            <input style={{ width: "100%" }} value={payload.contact_phone} onChange={(e) => setPayload({ ...payload, contact_phone: e.target.value })} />
          </label>
          <label>
            GSTIN
            <input style={{ width: "100%" }} value={payload.gstin} onChange={(e) => setPayload({ ...payload, gstin: e.target.value })} required />
          </label>
          <label>
            PAN
            <input style={{ width: "100%" }} value={payload.pan} onChange={(e) => setPayload({ ...payload, pan: e.target.value })} required />
          </label>
          <label>
            Registered address
            <textarea style={{ width: "100%" }} value={payload.registered_address} onChange={(e) => setPayload({ ...payload, registered_address: e.target.value })} />
          </label>
          <label>
            States covered (comma-separated)
            <input style={{ width: "100%" }} value={payload.coverage_states} onChange={(e) => setPayload({ ...payload, coverage_states: e.target.value })} />
          </label>
          <label>
            Cities covered (comma-separated)
            <input style={{ width: "100%" }} value={payload.coverage_cities} onChange={(e) => setPayload({ ...payload, coverage_cities: e.target.value })} />
          </label>
          <label>
            Years in business
            <input style={{ width: "100%" }} value={payload.years_in_business} onChange={(e) => setPayload({ ...payload, years_in_business: e.target.value })} />
          </label>
          <label>
            Employee count
            <input style={{ width: "100%" }} value={payload.employee_count} onChange={(e) => setPayload({ ...payload, employee_count: e.target.value })} />
          </label>
          <label>
            Annual turnover (INR)
            <input style={{ width: "100%" }} value={payload.annual_turnover} onChange={(e) => setPayload({ ...payload, annual_turnover: e.target.value })} />
          </label>
          <label>
            <input type="checkbox" checked={payload.gst_certificate} onChange={(e) => setPayload({ ...payload, gst_certificate: e.target.checked })} /> GST certificate available
          </label>
          <label>
            <input type="checkbox" checked={payload.pan_card} onChange={(e) => setPayload({ ...payload, pan_card: e.target.checked })} /> PAN card available
          </label>
          <button type="submit" disabled={busy}>
            {busy ? "Submitting…" : "Submit for review"}
          </button>
        </form>
      ) : null}
    </main>
  );
}
