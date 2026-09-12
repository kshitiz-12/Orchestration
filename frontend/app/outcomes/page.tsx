"use client";

import { AppShell } from "@/components/AppShell";
import { ReadinessBar, StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import { friendlyStatus, friendlyType } from "@/lib/labels";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

export default function OutcomesPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setBusy(true);
    api("/outcomes")
      .then((rows) => setRows(Array.isArray(rows) ? rows : []))
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }

  useEffect(() => {
    load();
  }, []);

  const statuses = useMemo(() => {
    const set = new Set(rows.map((r) => r.status).filter(Boolean));
    return ["ALL", ...Array.from(set).sort()];
  }, [rows]);

  const filtered = rows.filter((o) => {
    if (status !== "ALL" && o.status !== status) return false;
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return [o.case_reference, o.template_code, o.requester_email, o.title, o.status]
      .filter(Boolean)
      .some((v) => String(v).toLowerCase().includes(q));
  });

  return (
    <AppShell
      title="All requests"
      subtitle="Every email request the system is tracking."
      actions={
        <button className="btn secondary" onClick={load} disabled={busy}>
          {busy ? "Loading…" : "Refresh"}
        </button>
      }
    >
      {error && <p className="badge danger">{error}</p>}
      <div className="panel">
        <div className="toolbar">
          <input
            className="search"
            placeholder="Search by person, case number, or type…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s === "ALL" ? "All statuses" : friendlyStatus(s)}
              </option>
            ))}
          </select>
        </div>
        {filtered.length === 0 ? (
          <div className="empty">
            <strong>No matching requests</strong>
            Clear the search, or wait for a new email to arrive.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Case #</th>
                <th>What is it?</th>
                <th>From</th>
                <th>Opened</th>
                <th>Progress</th>
                <th>Blockers</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => (
                <tr key={o.outcome_id}>
                  <td>
                    <Link className="table-link" href={`/outcomes/${o.outcome_id}`}>
                      {o.case_reference}
                    </Link>
                    <div className="muted" style={{ fontSize: "0.78rem", marginTop: "0.2rem" }}>
                      {(o.title || "").slice(0, 42)}
                      {(o.title || "").length > 42 ? "…" : ""}
                    </div>
                  </td>
                  <td>
                    <span className="badge">{friendlyType(o.template_code)}</span>
                  </td>
                  <td>{o.requester_email}</td>
                  <td className="muted">{new Date(o.created_at).toLocaleString()}</td>
                  <td>
                    <ReadinessBar value={o.readiness_pct} />
                  </td>
                  <td className="muted">
                    {(o.blockers || []).length
                      ? `${(o.blockers || []).length} blocking`
                      : "None"}
                  </td>
                  <td>
                    <StatusBadge status={friendlyStatus(o.status)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </AppShell>
  );
}
