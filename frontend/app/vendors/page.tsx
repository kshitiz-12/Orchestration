"use client";

import { AppShell } from "@/components/AppShell";
import { AsEmpty, AsKpi, AsStatus } from "@/components/ui/PageBits";
import { api } from "@/lib/api";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

type Vendor = {
  vendor_id: string;
  name: string;
  category: string;
  contact_email: string;
  contact_name?: string | null;
  status: string;
  score?: number | null;
  vendor_tier?: string | null;
  gstin?: string | null;
  coverage_cities?: string[];
  coverage_states?: string[];
  invite_token?: string | null;
};

const CATEGORIES = [
  "Facilities Management",
  "AMC",
  "Supplies",
  "Repair & Maintenance",
  "Security",
  "Housekeeping",
  "IT/AV",
  "Pest Control",
  "Landscaping",
  "Other",
];

export default function VendorsPage() {
  const [rows, setRows] = useState<Vendor[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [scorecard, setScorecard] = useState<any>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const [invite, setInvite] = useState({
    name: "",
    contact_email: "",
    category: "Facilities Management",
    contact_name: "",
    service_areas: "",
  });

  const load = useCallback(async () => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (status) params.set("status", status);
    const list = await api<Vendor[]>(`/vendors?${params.toString()}`);
    setRows(list);
  }, [q, status]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("q")) setQ(params.get("q") as string);
    if (params.get("status")) setStatus(params.get("status") as string);
  }, []);

  useEffect(() => {
    load().catch((e) => setMsg(e.message || "Failed to load vendors"));
  }, [load]);

  const stats = useMemo(() => {
    const upper = (s: string) => String(s || "").toUpperCase();
    return {
      total: rows.length,
      active: rows.filter((r) => upper(r.status) === "ACTIVE").length,
      invited: rows.filter((r) => upper(r.status) === "INVITED").length,
      review: rows.filter((r) => ["REGISTERED", "UNDER_REVIEW", "PENDING"].includes(upper(r.status))).length,
    };
  }, [rows]);

  async function openDetail(id: string) {
    setBusy("detail");
    setMsg("");
    try {
      const detail = await api(`/vendors/${id}`);
      setSelected(detail);
      const card = await api(`/vendors/${id}/scorecard`).catch(() => null);
      setScorecard(card);
    } catch (e: any) {
      setMsg(e.message || "Failed to open vendor");
    } finally {
      setBusy("");
    }
  }

  async function sendInvite() {
    setBusy("invite");
    setMsg("");
    try {
      const res = await api("/vendors/invite", {
        method: "POST",
        body: JSON.stringify({
          name: invite.name,
          contact_email: invite.contact_email,
          category: invite.category,
          contact_name: invite.contact_name || null,
          service_areas: invite.service_areas
            ? invite.service_areas.split(",").map((s) => s.trim()).filter(Boolean)
            : [],
          send_email: true,
        }),
      });
      setMsg(`Invite sent. Open onboarding or share: ${res.registration_url}`);
      setInvite({
        name: "",
        contact_email: "",
        category: "Facilities Management",
        contact_name: "",
        service_areas: "",
      });
      setShowInvite(false);
      await load();
      if (res?.vendor?.vendor_id) {
        window.location.href = `/vendors/onboarding/${res.vendor.vendor_id}`;
      }
    } catch (e: any) {
      setMsg(e.message || "Invite failed");
    } finally {
      setBusy("");
    }
  }

  async function runScore(id: string) {
    setBusy("score");
    try {
      await api(`/vendors/${id}/score`, { method: "POST", body: "{}" });
      await openDetail(id);
      await load();
      setMsg("Score recomputed from submitted profile fields.");
    } catch (e: any) {
      setMsg(e.message || "Score failed");
    } finally {
      setBusy("");
    }
  }

  async function activate(id: string) {
    if (!window.confirm("Activate this vendor for work orders?")) return;
    setBusy("activate");
    try {
      await api(`/vendors/${id}/activate`, {
        method: "POST",
        body: JSON.stringify({ create_contract: true, notify: true }),
      });
      await openDetail(id);
      await load();
      setMsg("Vendor activated.");
    } catch (e: any) {
      setMsg(e.message || "Activate failed");
    } finally {
      setBusy("");
    }
  }

  async function suspend(id: string, blacklist = false) {
    const reason = window.prompt(blacklist ? "Blacklist reason" : "Suspend reason") || "";
    if (!reason.trim()) return;
    setBusy("suspend");
    try {
      await api(`/vendors/${id}/suspend`, {
        method: "POST",
        body: JSON.stringify({ reason, blacklist, notify: true }),
      });
      await openDetail(id);
      await load();
      setMsg(blacklist ? "Vendor blacklisted." : "Vendor suspended.");
    } catch (e: any) {
      setMsg(e.message || "Suspend failed");
    } finally {
      setBusy("");
    }
  }

  const v = selected?.vendor as Vendor | undefined;

  return (
    <AppShell
      title="Vendors"
      subtitle="Directory, invites, scoring and activation for facilities partners."
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Vendor Management", href: "/vendors" },
        { label: "Vendors" },
      ]}
      actions={
        <div className="row">
          <Link className="btn secondary" href="/vendors/onboarding">
            Onboarding pipeline
          </Link>
          <button type="button" className="btn accent" onClick={() => setShowInvite(true)}>
            + Invite vendor
          </button>
        </div>
      }
    >
      <div className="as-kpi-grid" style={{ marginBottom: "1rem" }}>
        <AsKpi label="Total vendors" value={stats.total} hint="In your directory" />
        <AsKpi label="Active" value={stats.active} hint="Usable on work orders" href="/vendors?status=ACTIVE" />
        <AsKpi label="Invited" value={stats.invited} hint="Awaiting registration" />
        <AsKpi label="In review" value={stats.review} hint="Submitted / pending" />
      </div>

      {msg ? (
        <div className="as-card" style={{ marginBottom: "1rem", borderColor: "#bfdbfe", background: "#eff6ff" }}>
          {msg}
        </div>
      ) : null}

      {showInvite ? (
        <div className="as-split" style={{ marginBottom: "1rem" }}>
          <section className="as-card">
            <div className="panel-head">
              <h2>Invite a vendor</h2>
              <button type="button" className="btn ghost" onClick={() => setShowInvite(false)}>
                Cancel
              </button>
            </div>
            <div className="as-form-grid">
              <label className="as-field">
                <span className="as-label">Company name *</span>
                <input
                  value={invite.name}
                  onChange={(e) => setInvite({ ...invite, name: e.target.value })}
                  placeholder="Legal / trade name"
                />
              </label>
              <label className="as-field">
                <span className="as-label">Contact email *</span>
                <input
                  value={invite.contact_email}
                  onChange={(e) => setInvite({ ...invite, contact_email: e.target.value })}
                  placeholder="vendor@company.com"
                />
              </label>
              <label className="as-field">
                <span className="as-label">Contact name</span>
                <input
                  value={invite.contact_name}
                  onChange={(e) => setInvite({ ...invite, contact_name: e.target.value })}
                />
              </label>
              <label className="as-field">
                <span className="as-label">Vendor type</span>
                <select
                  value={invite.category}
                  onChange={(e) => setInvite({ ...invite, category: e.target.value })}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
              <label className="as-field span-2">
                <span className="as-label">Coverage cities</span>
                <input
                  value={invite.service_areas}
                  onChange={(e) => setInvite({ ...invite, service_areas: e.target.value })}
                  placeholder="Delhi, Mumbai, Bengaluru"
                />
              </label>
            </div>
            <div className="row" style={{ marginTop: "1rem", justifyContent: "flex-end" }}>
              <button
                type="button"
                className="btn accent"
                disabled={busy === "invite" || !invite.name || !invite.contact_email}
                onClick={sendInvite}
              >
                {busy === "invite" ? "Sending…" : "Send invite & open onboarding"}
              </button>
            </div>
          </section>
          <aside className="as-side-help">
            <h3>How invites work</h3>
            <p>We create the vendor as INVITED and email a registration link.</p>
            <ul>
              <li>Same 6-step form on company and vendor sides</li>
              <li>Activate only after review</li>
              <li>Only ACTIVE vendors appear on work orders</li>
            </ul>
          </aside>
        </div>
      ) : null}

      <div className="as-split">
        <section className="as-card">
          <div className="panel-head">
            <h2>Vendor directory</h2>
          </div>
          <div className="as-toolbar">
            <input
              className="search"
              placeholder="Search name, email, category…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              <option value="INVITED">Invited</option>
              <option value="REGISTERED">Registered</option>
              <option value="UNDER_REVIEW">Under review</option>
              <option value="ACTIVE">Active</option>
              <option value="SUSPENDED">Suspended</option>
            </select>
            <button type="button" className="btn secondary" onClick={() => load()} disabled={!!busy}>
              Refresh
            </button>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Vendor</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Score</th>
                  <th>Tier</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.vendor_id}>
                    <td>
                      <strong>{row.name}</strong>
                      <div className="muted" style={{ fontSize: 12 }}>
                        {row.contact_email}
                      </div>
                    </td>
                    <td>{row.category}</td>
                    <td>
                      <AsStatus status={row.status} />
                    </td>
                    <td>{row.score ?? "—"}</td>
                    <td>{row.vendor_tier ?? "—"}</td>
                    <td>
                      <div className="row" style={{ gap: "0.35rem", justifyContent: "flex-end" }}>
                        <button type="button" className="btn ghost" onClick={() => openDetail(row.vendor_id)}>
                          Details
                        </button>
                        <Link className="btn secondary" href={`/vendors/onboarding/${row.vendor_id}`}>
                          Onboarding
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!rows.length ? (
            <AsEmpty
              title="No vendors yet"
              body="Invite a partner to start the six-step onboarding wizard."
              action={
                <button type="button" className="btn accent" onClick={() => setShowInvite(true)}>
                  + Invite vendor
                </button>
              }
            />
          ) : null}
        </section>

        <section className="as-card">
          <div className="panel-head">
            <h2>{v ? v.name : "Vendor detail"}</h2>
            {v ? <AsStatus status={v.status} /> : null}
          </div>
          {!v ? (
            <AsEmpty title="Select a vendor" body="Open Details on a row to score, activate, or resend the invite." />
          ) : (
            <div className="stack">
              <div className="as-form-grid">
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    Contact
                  </div>
                  <div>
                    {v.contact_name || "—"} · {v.contact_email}
                  </div>
                </div>
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    Category
                  </div>
                  <div>{v.category}</div>
                </div>
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    Score / tier
                  </div>
                  <div>
                    {v.score ?? "—"} · {v.vendor_tier ?? "—"}
                  </div>
                </div>
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    GSTIN
                  </div>
                  <div>{v.gstin || "—"}</div>
                </div>
              </div>
              <div className="row" style={{ gap: "0.45rem" }}>
                <Link className="btn accent" href={`/vendors/onboarding/${v.vendor_id}`}>
                  Open onboarding
                </Link>
                <button type="button" className="btn secondary" disabled={!!busy} onClick={() => runScore(v.vendor_id)}>
                  Recompute score
                </button>
                {String(v.status).toUpperCase() !== "ACTIVE" ? (
                  <button type="button" className="btn" disabled={!!busy} onClick={() => activate(v.vendor_id)}>
                    Activate
                  </button>
                ) : null}
                <button type="button" className="btn ghost" disabled={!!busy} onClick={() => suspend(v.vendor_id, false)}>
                  Suspend
                </button>
              </div>
              {scorecard ? (
                <div className="as-side-help" style={{ background: "#f8fafc", borderColor: "#e2e8f0" }}>
                  <h3 style={{ color: "#0f172a" }}>Scorecard</h3>
                  <p>Tier {scorecard.tier || v.vendor_tier || "—"} · score {scorecard.score ?? v.score ?? "—"}</p>
                </div>
              ) : null}
              <button
                type="button"
                className="btn secondary"
                disabled={!!busy}
                onClick={async () => {
                  setBusy("resend");
                  try {
                    const res = await api(`/vendors/${v.vendor_id}/resend-invite`, { method: "POST", body: "{}" });
                    setMsg(`Invite resent: ${res.registration_url || "ok"}`);
                    await openDetail(v.vendor_id);
                  } catch (e: any) {
                    setMsg(e.message || "Resend failed");
                  } finally {
                    setBusy("");
                  }
                }}
              >
                Resend invite mail
              </button>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
