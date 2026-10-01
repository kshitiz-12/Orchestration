"use client";

import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import { friendlyPriority, friendlyStatus, friendlyWaitingOn, priorityTone, requestType } from "@/lib/labels";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

export default function OutcomesPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [type, setType] = useState("ALL");
  const [dept, setDept] = useState("ALL");
  const [waiting, setWaiting] = useState("ALL");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    setBusy(true);
    api("/outcomes?limit=300")
      .then((rows) => setRows(Array.isArray(rows) ? rows : []))
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }

  useEffect(() => {
    // Deep links from the home page: /outcomes?type=Parking or ?department=IT%20Support
    const params = new URLSearchParams(window.location.search);
    if (params.get("type")) setType(params.get("type") as string);
    if (params.get("department")) setDept(params.get("department") as string);
    if (params.get("waiting")) setWaiting(params.get("waiting") as string);
    load();
  }, []);

  const options = useMemo(() => {
    const uniq = (vals: any[]) => ["ALL", ...Array.from(new Set(vals.filter(Boolean))).sort()];
    return {
      statuses: uniq(rows.map((r) => r.status)),
      types: uniq(rows.map((r) => requestType(r))),
      depts: uniq(rows.map((r) => r.department)),
    };
  }, [rows]);

  const filtered = rows.filter((o) => {
    if (status !== "ALL" && o.status !== status) return false;
    if (type !== "ALL" && requestType(o) !== type) return false;
    if (dept !== "ALL" && o.department !== dept) return false;
    if (waiting !== "ALL" && o.waiting_on !== waiting) return false;
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return [o.case_reference, requestType(o), o.department, o.requester_email, o.title, o.status]
      .filter(Boolean)
      .some((v) => String(v).toLowerCase().includes(q));
  });

  return (
    <AppShell
      title="All requests"
      subtitle="Every request the desk is tracking - repairs, IT, visitors, travel, rooms and more."
      actions={
        <button className="btn secondary" onClick={load} disabled={busy}>
          {busy ? "Loading…" : "Refresh"}
        </button>
      }
    >
      {error && <p className="badge danger">{error}</p>}
      <div className="panel">
        <div className="toolbar" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
          <input
            className="search"
            placeholder="Search by person, case number, type or team…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select className="select" value={type} onChange={(e) => setType(e.target.value)}>
            {options.types.map((s) => (
              <option key={s} value={s}>{s === "ALL" ? "All types" : s}</option>
            ))}
          </select>
          <select className="select" value={dept} onChange={(e) => setDept(e.target.value)}>
            {options.depts.map((s) => (
              <option key={s} value={s}>{s === "ALL" ? "All teams" : s}</option>
            ))}
          </select>
          <select className="select" value={waiting} onChange={(e) => setWaiting(e.target.value)}>
            {["ALL", "requester", "approver", "team", "admin"].map((s) => (
              <option key={s} value={s}>{s === "ALL" ? "Waiting on anyone" : `Waiting on ${friendlyWaitingOn(s).toLowerCase()}`}</option>
            ))}
          </select>
          <select className="select" value={status} onChange={(e) => setStatus(e.target.value)}>
            {options.statuses.map((s) => (
              <option key={s} value={s}>{s === "ALL" ? "All statuses" : friendlyStatus(s)}</option>
            ))}
          </select>
        </div>
        {filtered.length === 0 ? (
          <div className="empty">
            <strong>No matching requests</strong>
            Clear the filters, or wait for a new email to arrive.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Case #</th>
                <th>Type</th>
                <th>Team</th>
                <th>From</th>
                <th>Priority</th>
                <th>Waiting on</th>
                <th>Due</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => {
                const overdue = o.due_at && new Date(o.due_at + "Z") < new Date() && !["CLOSED", "RESOLVED", "CANCELLED"].includes(o.status);
                return (
                  <tr key={o.outcome_id}>
                    <td>
                      <Link className="table-link" href={`/outcomes/${o.outcome_id}`}>
                        {o.case_reference}
                      </Link>
                      <div className="muted" style={{ fontSize: "0.78rem", marginTop: "0.2rem" }}>
                        {(o.title || "").slice(0, 46)}
                        {(o.title || "").length > 46 ? "…" : ""}
                      </div>
                    </td>
                    <td><span className="badge">{requestType(o)}</span></td>
                    <td className="muted">{o.department || "—"}</td>
                    <td>{o.requester_email}</td>
                    <td><span className={`badge ${priorityTone(o.priority)}`}>{friendlyPriority(o.priority)}</span></td>
                    <td className="muted">{friendlyWaitingOn(o.waiting_on)}</td>
                    <td className={overdue ? "" : "muted"} style={overdue ? { color: "var(--danger)", fontWeight: 600 } : undefined}>
                      {o.due_at ? new Date(o.due_at + "Z").toLocaleString([], { dateStyle: "short", timeStyle: "short" }) : "—"}
                      {overdue ? " · overdue" : ""}
                    </td>
                    <td><StatusBadge status={friendlyStatus(o.status)} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </AppShell>
  );
}
