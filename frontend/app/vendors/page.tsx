"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useCallback, useEffect, useState } from "react";

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

export default function VendorsPage() {
  const [rows, setRows] = useState<Vendor[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [scorecard, setScorecard] = useState<any>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const [invite, setInvite] = useState({
    name: "",
    contact_email: "",
    category: "hvac",
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
    load().catch((e) => setMsg(e.message || "Failed to load vendors"));
  }, [load]);

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
      setMsg(`Invited. Registration link: ${res.registration_url}`);
      setInvite({ name: "", contact_email: "", category: "hvac", contact_name: "", service_areas: "" });
      await load();
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
      await api(`/vendors/${id}/activate`, { method: "POST", body: JSON.stringify({ create_contract: true, notify: true }) });
      await openDetail(id);
      await load();
      setMsg("Vendor activated — desk can now use them.");
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
      subtitle="Invite, review, score and activate vendors. Only ACTIVE vendors are used on work orders."
    >
      <div className="stack">
        {msg ? <div className="panel muted">{msg}</div> : null}

        <div className="panel">
          <h2>Invite vendor</h2>
          <div className="row" style={{ flexWrap: "wrap", gap: "0.75rem" }}>
            <input placeholder="Company name" value={invite.name} onChange={(e) => setInvite({ ...invite, name: e.target.value })} />
            <input placeholder="Contact email" value={invite.contact_email} onChange={(e) => setInvite({ ...invite, contact_email: e.target.value })} />
            <input placeholder="Contact name" value={invite.contact_name} onChange={(e) => setInvite({ ...invite, contact_name: e.target.value })} />
            <input placeholder="Category (hvac, maintenance…)" value={invite.category} onChange={(e) => setInvite({ ...invite, category: e.target.value })} />
            <input placeholder="Cities (comma-separated)" value={invite.service_areas} onChange={(e) => setInvite({ ...invite, service_areas: e.target.value })} />
            <button className="btn" disabled={busy === "invite" || !invite.name || !invite.contact_email} onClick={sendInvite}>
              Send invite email
            </button>
          </div>
        </div>

        <div className="panel">
          <h2>Vendor directory</h2>
          <div className="row" style={{ gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            <input placeholder="Search name / GST / PAN" value={q} onChange={(e) => setQ(e.target.value)} />
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              <option value="INVITED">INVITED</option>
              <option value="UNDER_REVIEW">UNDER_REVIEW</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="SUSPENDED">SUSPENDED</option>
              <option value="BLACKLISTED">BLACKLISTED</option>
            </select>
            <button className="btn secondary" onClick={() => load()}>
              Refresh
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
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
                    {row.name}
                    <div className="muted" style={{ fontSize: 12 }}>
                      {row.contact_email}
                    </div>
                  </td>
                  <td>{row.category}</td>
                  <td>{row.status}</td>
                  <td>{row.score ?? "—"}</td>
                  <td>{row.vendor_tier ?? "—"}</td>
                  <td>
                    <button className="btn secondary" onClick={() => openDetail(row.vendor_id)}>
                      Open
                    </button>
                  </td>
                </tr>
              ))}
              {!rows.length ? (
                <tr>
                  <td colSpan={6} className="muted">
                    No vendors yet — send an invite above.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>

        {v ? (
          <div className="panel">
            <h2>
              {v.name}{" "}
              <span className="muted">
                ({v.status}
                {v.score != null ? ` · ${v.score}` : ""}
                {v.vendor_tier ? ` · ${v.vendor_tier}` : ""})
              </span>
            </h2>
            <p className="muted">
              {v.contact_name || "—"} · {v.contact_email} · GST {v.gstin || "—"}
            </p>
            <p>
              Coverage: {(v.coverage_states || []).join(", ") || "—"} / {(v.coverage_cities || []).join(", ") || "—"}
            </p>
            {selected?.registration_url ? (
              <p>
                Registration link: <code>{selected.registration_url}</code>
              </p>
            ) : null}
            <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap" }}>
              <button className="btn secondary" disabled={!!busy} onClick={() => runScore(v.vendor_id)}>
                Recompute score
              </button>
              {v.status !== "ACTIVE" && v.status !== "BLACKLISTED" ? (
                <button className="btn" disabled={!!busy} onClick={() => activate(v.vendor_id)}>
                  Activate
                </button>
              ) : null}
              {v.status === "ACTIVE" || v.status === "UNDER_REVIEW" ? (
                <button className="btn secondary" disabled={!!busy} onClick={() => suspend(v.vendor_id, false)}>
                  Suspend
                </button>
              ) : null}
              {v.status !== "BLACKLISTED" ? (
                <button className="btn secondary" disabled={!!busy} onClick={() => suspend(v.vendor_id, true)}>
                  Blacklist
                </button>
              ) : null}
              {(v.status === "INVITED" || v.status === "UNDER_REVIEW") && (
                <button
                  className="btn secondary"
                  disabled={!!busy}
                  onClick={async () => {
                    setBusy("resend");
                    try {
                      const res = await api(`/vendors/${v.vendor_id}/resend-invite`, { method: "POST", body: "{}" });
                      setMsg(`Invite resent: ${res.registration_url}`);
                      await openDetail(v.vendor_id);
                    } catch (e: any) {
                      setMsg(e.message || "Resend failed");
                    } finally {
                      setBusy("");
                    }
                  }}
                >
                  Resend invite
                </button>
              )}
            </div>
            {selected?.vendor?.score_breakdown ? (
              <pre style={{ marginTop: "1rem", whiteSpace: "pre-wrap" }}>
                {JSON.stringify(selected.vendor.score_breakdown, null, 2)}
              </pre>
            ) : null}
            {scorecard ? (
              <div style={{ marginTop: "1rem" }}>
                <h3>Ledger scorecard</h3>
                <p className="muted">{scorecard.note}</p>
                <p>
                  WOs seen: {scorecard.work_orders_seen} · Completions: {scorecard.completions_seen} · Spend: INR{" "}
                  {scorecard.spend_recorded}
                </p>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </AppShell>
  );
}
