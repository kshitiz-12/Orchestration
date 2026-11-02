"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AsEmpty, AsKpi, AsStatus } from "@/components/ui/PageBits";
import { api } from "@/lib/api";

type Vendor = {
  vendor_id: string;
  name: string;
  category: string;
  contact_email: string;
  contact_name?: string | null;
  status: string;
  score?: number | null;
  vendor_tier?: string | null;
};

const CATEGORIES = [
  "Facilities Management",
  "AMC",
  "Supplies",
  "Repair & Maintenance",
  "Security",
  "Housekeeping",
  "IT/AV",
  "Other",
];

export default function VendorOnboardingListPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Vendor[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const [filter, setFilter] = useState("pipeline");
  const [invite, setInvite] = useState({
    name: "",
    contact_email: "",
    category: "Facilities Management",
    contact_name: "",
    service_areas: "",
  });

  const load = useCallback(async () => {
    const list = await api<Vendor[]>("/vendors");
    setRows(list);
  }, []);

  useEffect(() => {
    load().catch((e) => setMsg(e.message || "Failed to load vendors"));
  }, [load]);

  const stats = useMemo(() => {
    const u = (s: string) => String(s || "").toUpperCase();
    return {
      invited: rows.filter((r) => u(r.status) === "INVITED").length,
      inProgress: rows.filter((r) =>
        ["REGISTERED", "UNDER_REVIEW", "PENDING", "DRAFT"].includes(u(r.status))
      ).length,
      active: rows.filter((r) => u(r.status) === "ACTIVE").length,
      total: rows.length,
    };
  }, [rows]);

  const visible = useMemo(() => {
    const u = (s: string) => String(s || "").toUpperCase();
    if (filter === "pipeline") {
      return rows.filter((r) =>
        ["INVITED", "REGISTERED", "UNDER_REVIEW", "PENDING", "DRAFT"].includes(u(r.status))
      );
    }
    if (filter === "active") return rows.filter((r) => u(r.status) === "ACTIVE");
    return rows;
  }, [rows, filter]);

  async function startOnboarding() {
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
      setShowInvite(false);
      setInvite({ name: "", contact_email: "", category: "Facilities Management", contact_name: "", service_areas: "" });
      await load();
      router.push(`/vendors/onboarding/${res.vendor.vendor_id}`);
    } catch (e: any) {
      setMsg(e.message || "Could not start onboarding");
    } finally {
      setBusy("");
    }
  }

  return (
    <AppShell
      title="Vendor Onboarding"
      subtitle="Register a new vendor for Facilities, AMC, Supplies or other admin services."
      breadcrumbs={[
        { label: "Vendor Management", href: "/vendors" },
        { label: "Onboarding" },
      ]}
      actions={
        <button type="button" className="btn accent" onClick={() => setShowInvite(true)}>
          + New vendor
        </button>
      }
    >
      <div className="as-kpi-grid" style={{ marginBottom: "1rem" }}>
        <button type="button" className={`as-kpi ${filter === "pipeline" ? "on" : ""}`} onClick={() => setFilter("pipeline")}>
          <span className="label">In pipeline</span>
          <span className="value">{stats.invited + stats.inProgress}</span>
          <span className="hint">{stats.invited} invited · {stats.inProgress} in review</span>
        </button>
        <button type="button" className={`as-kpi ${filter === "active" ? "on" : ""}`} onClick={() => setFilter("active")}>
          <span className="label">Active vendors</span>
          <span className="value">{stats.active}</span>
          <span className="hint">Ready for work orders</span>
        </button>
        <AsKpi label="All vendors" value={stats.total} hint="Directory total" />
        <button type="button" className="as-kpi" onClick={() => setShowInvite(true)}>
          <span className="label">Start onboarding</span>
          <span className="value" style={{ fontSize: "1.35rem" }}>Invite →</span>
          <span className="hint">Mail link + company draft</span>
        </button>
      </div>

      {msg ? <p className="badge danger" style={{ marginBottom: "0.85rem" }}>{msg}</p> : null}

      <section className="as-card">
        <div className="panel-head">
          <h2>{filter === "pipeline" ? "Onboarding pipeline" : filter === "active" ? "Active vendors" : "All vendors"}</h2>
          <div className="as-tabs" style={{ border: "none", margin: 0, padding: 0, borderRadius: 0 }}>
            {[
              { id: "pipeline", label: "Pipeline" },
              { id: "active", label: "Active" },
              { id: "all", label: "All" },
            ].map((t) => (
              <button key={t.id} type="button" className={filter === t.id ? "on" : ""} onClick={() => setFilter(t.id)}>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {!visible.length ? (
          <AsEmpty
            title="No vendors in this view"
            body="Invite a vendor to open the six-step onboarding wizard — same UI they get from the mail link."
          />
        ) : (
          <div className="vo-table-wrap">
            <table className="vo-table">
              <thead>
                <tr>
                  <th>Vendor</th>
                  <th>Category</th>
                  <th>Contact</th>
                  <th>Status</th>
                  <th>Score</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((v) => (
                  <tr key={v.vendor_id}>
                    <td>
                      <strong>{v.name}</strong>
                      {v.contact_name ? (
                        <div className="muted" style={{ fontSize: "0.78rem" }}>{v.contact_name}</div>
                      ) : null}
                    </td>
                    <td>{v.category}</td>
                    <td className="mono" style={{ fontSize: "0.82rem" }}>{v.contact_email}</td>
                    <td>
                      <AsStatus status={v.status} />
                    </td>
                    <td>{v.score != null ? v.score : "—"}</td>
                    <td>
                      <Link className="btn secondary" href={`/vendors/onboarding/${v.vendor_id}`}>
                        Open wizard
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {showInvite ? (
        <div className="as-modal-backdrop" onClick={() => setShowInvite(false)}>
          <div className="as-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="as-modal-head">
              <div>
                <h2>Invite vendor</h2>
                <p className="muted" style={{ margin: 0 }}>
                  Creates the record, mails the registration link, and opens the company draft.
                </p>
              </div>
              <button type="button" className="as-modal-x" onClick={() => setShowInvite(false)}>
                ×
              </button>
            </div>
            <div className="as-form-grid">
              <label className="as-field">
                <span className="as-label">Legal / trade name *</span>
                <input
                  value={invite.name}
                  onChange={(e) => setInvite({ ...invite, name: e.target.value })}
                  placeholder="ABC Facilities Services Pvt. Ltd."
                />
              </label>
              <label className="as-field">
                <span className="as-label">Vendor email *</span>
                <input
                  value={invite.contact_email}
                  onChange={(e) => setInvite({ ...invite, contact_email: e.target.value })}
                  placeholder="vendor@example.com"
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
                <span className="as-label">Category</span>
                <select
                  value={invite.category}
                  onChange={(e) => setInvite({ ...invite, category: e.target.value })}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label className="as-field span-2">
                <span className="as-label">Service cities</span>
                <input
                  value={invite.service_areas}
                  onChange={(e) => setInvite({ ...invite, service_areas: e.target.value })}
                  placeholder="Delhi, Gurgaon, Mumbai"
                />
              </label>
            </div>
            <div className="as-modal-actions">
              <button type="button" className="btn secondary" onClick={() => setShowInvite(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="btn accent"
                disabled={Boolean(busy) || !invite.name || !invite.contact_email}
                onClick={startOnboarding}
              >
                {busy === "invite" ? "Starting…" : "Invite & open wizard"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
