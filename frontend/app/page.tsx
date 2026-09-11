"use client";

import { AppShell } from "@/components/AppShell";
import { ReadinessBar, StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

export default function HomePage() {
  const [kpis, setKpis] = useState<any>(null);
  const [outcomes, setOutcomes] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [k, o] = await Promise.all([api("/dashboard/kpis"), api("/outcomes?limit=12")]);
      setKpis(k && typeof k === "object" ? k : null);
      setOutcomes(Array.isArray(o) ? o : []);
      setUpdatedAt(new Date());
    } catch (e: any) {
      setError(e.message || "Failed to load");
      setOutcomes([]);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const filtered = outcomes.filter((o) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return [o.case_reference, o.template_code, o.requester_email, o.status, o.title]
      .filter(Boolean)
      .some((v) => String(v).toLowerCase().includes(q));
  });

  const kpiCards = [
    { label: "Active outcomes", value: kpis?.outcomes_active, href: "/outcomes", hint: "Open cases" },
    { label: "At risk", value: kpis?.at_risk, href: "/outcomes", hint: "Needs attention" },
    { label: "Overdue tasks", value: kpis?.overdue_tasks, href: "/tasks", hint: "Past due" },
    { label: "Approvals", value: kpis?.pending_approvals, href: "/reviews", hint: "Waiting humans" },
    { label: "Human reviews", value: kpis?.human_reviews, href: "/reviews", hint: "AI queue" },
    { label: "Failures", value: kpis?.failures, href: "/failures", hint: "Reprocess" },
  ];

  return (
    <AppShell
      title="Operations"
      subtitle="Live view of email intake, AI interpretation, and governed outcomes."
      actions={
        <>
          <span className="muted" style={{ fontSize: "0.82rem" }}>
            {updatedAt ? `Updated ${updatedAt.toLocaleTimeString()}` : "—"}
          </span>
          <button className="btn secondary" onClick={load} disabled={busy}>
            {busy ? "Refreshing…" : "Refresh"}
          </button>
          <Link className="btn accent" href="/email">
            CloudMailin
          </Link>
        </>
      }
    >
      {error && (
        <div className="panel" style={{ marginBottom: "1rem", borderColor: "#fecdd3" }}>
          <strong style={{ color: "var(--danger)" }}>Could not load dashboard</strong>
          <p className="muted" style={{ margin: "0.35rem 0 0" }}>{error}</p>
          <button className="btn secondary" style={{ marginTop: "0.75rem" }} onClick={load}>
            Retry
          </button>
        </div>
      )}

      {busy && !kpis && !error && (
        <div className="panel" style={{ marginBottom: "1rem" }}>
          <strong>Loading from Render…</strong>
          <p className="muted" style={{ margin: "0.35rem 0 0" }}>
            Free tier may take 30–60s to wake. Keep this tab open.
          </p>
        </div>
      )}

      <div className="grid kpis">
        {kpiCards.map((k) => (
          <Link key={k.label} href={k.href} className="kpi clickable">
            <div className="label">{k.label}</div>
            <div className="value">{k.value ?? "—"}</div>
            <div className="hint">{k.hint}</div>
          </Link>
        ))}
      </div>

      <div className="grid actions">
        <Link href="/email" className="action-tile">
          <strong>Ingest email</strong>
          <span>CloudMailin webhook status, SMTP replies, and setup checklist.</span>
        </Link>
        <Link href="/reviews" className="action-tile">
          <strong>Clear review queue</strong>
          <span>Accept, clarify, or reject low-confidence AI interpretations.</span>
        </Link>
        <Link href="/outcomes" className="action-tile">
          <strong>Browse outcomes</strong>
          <span>Parent business results with readiness, blockers, and audit.</span>
        </Link>
        <Link href="/failures" className="action-tile">
          <strong>Failure console</strong>
          <span>Inspect failed processing jobs and retry safely.</span>
        </Link>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Recent cases</h2>
          <Link href="/outcomes" className="btn ghost">
            View all
          </Link>
        </div>
        <div className="toolbar">
          <input
            className="search"
            placeholder="Search case, requester, type, status…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {filtered.length === 0 ? (
          <div className="empty">
            <strong>No cases yet</strong>
            Send mail to your CloudMailin address to create the first outcome.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Case</th>
                <th>Type</th>
                <th>Requester</th>
                <th>Status</th>
                <th>Readiness</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o) => (
                <tr key={o.outcome_id}>
                  <td>
                    <Link className="table-link" href={`/outcomes/${o.outcome_id}`}>
                      {o.case_reference}
                    </Link>
                  </td>
                  <td>
                    <span className="badge">{o.template_code}</span>
                  </td>
                  <td className="mono">{o.requester_email}</td>
                  <td>
                    <StatusBadge status={o.status} />
                  </td>
                  <td>
                    <ReadinessBar value={o.readiness_pct} />
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
