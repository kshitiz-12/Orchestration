"use client";

import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import { friendlyPriority, friendlyStatus, priorityTone, requestType } from "@/lib/labels";
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
    return [o.case_reference, requestType(o), o.department, o.requester_email, o.status, o.title]
      .filter(Boolean)
      .some((v) => String(v).toLowerCase().includes(q));
  });

  const waitingReviews = Number(kpis?.human_reviews || 0) + Number(kpis?.pending_approvals || 0);
  const pendingConfirm = Number(kpis?.pending_confirmations || 0);
  const awaitingReqs = Number(kpis?.awaiting_requirements || 0);
  const waitingYou =
    kpis?.waiting_on_you != null
      ? Number(kpis.waiting_on_you)
      : waitingReviews + pendingConfirm;
  const pastSla = Number(kpis?.past_sla || 0);
  const late = Number(kpis?.overdue_tasks || 0) + pastSla;
  const urgent = Number(kpis?.urgent_open || 0);
  const problems = Number(kpis?.failures || 0);
  const openCases = Number(kpis?.outcomes_active || 0);
  const needsAttention = Number(kpis?.at_risk || 0) + awaitingReqs + Number(kpis?.no_resource || 0);
  const byType: { label: string; count: number }[] = Array.isArray(kpis?.open_by_type) ? kpis.open_by_type : [];
  const byDept: { label: string; count: number }[] = Array.isArray(kpis?.open_by_department) ? kpis.open_by_department : [];

  const nextSteps: { title: string; detail: string; href: string; tone: "warn" | "danger" | "ok" | "neutral" }[] = [];
  if (urgent > 0) {
    nextSteps.push({
      title: `${urgent} urgent request${urgent === 1 ? "" : "s"} open`,
      detail: "Safety or work-stopping issues - the team and you were alerted when they came in.",
      href: "/outcomes",
      tone: "danger",
    });
  }
  if (pastSla > 0) {
    nextSteps.push({
      title: `${pastSla} request${pastSla === 1 ? "" : "s"} past due`,
      detail: "The team missed the agreed time. Chase them or reassign from the request page.",
      href: "/outcomes",
      tone: "warn",
    });
  }
  if (waitingYou > 0) {
    const bits: string[] = [];
    if (waitingReviews > 0) bits.push(`${waitingReviews} approval/review`);
    if (pendingConfirm > 0) bits.push(`${pendingConfirm} booking to confirm`);
    nextSteps.push({
      title: `${waitingYou} item${waitingYou === 1 ? "" : "s"} waiting for your decision`,
      detail: bits.length ? bits.join(" · ") : "Open these first — the system paused until someone decides.",
      href: "/reviews",
      tone: "warn",
    });
  }
  if (awaitingReqs > 0) {
    nextSteps.push({
      title: `${awaitingReqs} request${awaitingReqs === 1 ? "" : "s"} still missing details`,
      detail: "We already emailed the requester for only the remaining gaps.",
      href: "/outcomes?waiting=requester",
      tone: "neutral",
    });
  }
  if (Number(kpis?.overdue_tasks || 0) > 0) {
    const n = Number(kpis.overdue_tasks);
    nextSteps.push({
      title: `${n} late task${n === 1 ? "" : "s"}`,
      detail: "Someone still needs to finish work on these requests.",
      href: "/tasks",
      tone: "warn",
    });
  }
  if (problems > 0) {
    nextSteps.push({
      title: `${problems} processing problem${problems === 1 ? "" : "s"}`,
      detail: "An email or job failed. Tech can retry from Failures.",
      href: "/failures",
      tone: "danger",
    });
  }
  if (nextSteps.length === 0 && openCases > 0) {
    nextSteps.push({
      title: "Nothing urgent right now",
      detail: `${openCases} open request${openCases === 1 ? "" : "s"} are moving along.`,
      href: "/outcomes",
      tone: "ok",
    });
  }
  if (nextSteps.length === 0) {
    nextSteps.push({
      title: "No open requests yet",
      detail: "When someone emails the intake address, their request will show up here.",
      href: "/email",
      tone: "neutral",
    });
  }

  return (
    <AppShell
      title="Home"
      subtitle="See what needs your attention, then open the request."
      actions={
        <>
          <span className="muted" style={{ fontSize: "0.82rem" }}>
            {updatedAt ? `Updated ${updatedAt.toLocaleTimeString()}` : "—"}
          </span>
          <button className="btn secondary" onClick={load} disabled={busy}>
            {busy ? "Refreshing…" : "Refresh"}
          </button>
        </>
      }
    >
      {error && (
        <div className="panel" style={{ marginBottom: "1rem", borderColor: "#fecdd3" }}>
          <strong style={{ color: "var(--danger)" }}>Couldn’t load the page</strong>
          <p className="muted" style={{ margin: "0.35rem 0 0" }}>{error}</p>
          <button className="btn secondary" style={{ marginTop: "0.75rem" }} onClick={load}>
            Try again
          </button>
        </div>
      )}

      {busy && !kpis && !error && (
        <div className="panel" style={{ marginBottom: "1rem" }}>
          <strong>Loading…</strong>
          <p className="muted" style={{ margin: "0.35rem 0 0" }}>
            First load can take up to a minute if the server was asleep.
          </p>
        </div>
      )}

      <div className="panel next-panel" style={{ marginBottom: "1.1rem" }}>
        <div className="panel-head">
          <h2>What should I do next?</h2>
        </div>
        <div className="stack">
          {nextSteps.map((step) => (
            <Link key={step.title} href={step.href} className={`next-card tone-${step.tone}`}>
              <strong>{step.title}</strong>
              <span>{step.detail}</span>
            </Link>
          ))}
        </div>
      </div>

      <div className="grid kpis">
        <Link href="/outcomes" className="kpi clickable">
          <div className="label">Open requests</div>
          <div className="value">{openCases || "—"}</div>
          <div className="hint">Cases still being handled</div>
        </Link>
        <Link href="/outcomes" className="kpi clickable">
          <div className="label">Need attention</div>
          <div className="value">{needsAttention || "—"}</div>
          <div className="hint">At risk or stuck</div>
        </Link>
        <Link href="/reviews" className="kpi clickable">
          <div className="label">Waiting on you</div>
          <div className="value">{waitingYou || "—"}</div>
          <div className="hint">Approvals, reviews and confirmations</div>
        </Link>
        <Link href="/outcomes" className="kpi clickable">
          <div className="label">Late work</div>
          <div className="value">{late || "—"}</div>
          <div className="hint">
            Past due{kpis?.resolved_24h != null ? ` · ${kpis.resolved_24h} resolved in 24h` : ""}
          </div>
        </Link>
        <div className="kpi">
          <div className="label">Automation (30 days)</div>
          <div className="value">{kpis?.automation_rate_pct != null ? `${kpis.automation_rate_pct}%` : "—"}</div>
          <div className="hint">
            Routine steps done without a human
            {kpis?.verified_closure_pct != null ? ` · ${kpis.verified_closure_pct}% closures verified` : ""}
          </div>
        </div>
      </div>

      {kpis?.ai_emergency_stop && (
        <div className="panel" style={{ marginBottom: "1.1rem", borderColor: "var(--danger)" }}>
          <strong>AI is paused (emergency stop).</strong> Requests are still logged and safety issues still go out
          urgently, but every other request waits for your approval. Turn off AI_EMERGENCY_STOP to resume.
        </div>
      )}

      {(byType.length > 0 || byDept.length > 0) && (
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem", marginBottom: "1.1rem" }}>
          <div className="panel">
            <div className="panel-head"><h2>Open by type</h2></div>
            <div className="stack" style={{ gap: "0.35rem" }}>
              {byType.slice(0, 10).map((r) => (
                <Link key={r.label} href={`/outcomes?type=${encodeURIComponent(r.label)}`} className="table-link"
                  style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>{r.label}</span><strong>{r.count}</strong>
                </Link>
              ))}
            </div>
          </div>
          <div className="panel">
            <div className="panel-head"><h2>Open by team</h2></div>
            <div className="stack" style={{ gap: "0.35rem" }}>
              {byDept.slice(0, 10).map((r) => (
                <Link key={r.label} href={`/outcomes?department=${encodeURIComponent(r.label)}`} className="table-link"
                  style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>{r.label}</span><strong>{r.count}</strong>
                </Link>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="grid actions">
        <Link href="/reviews" className="action-tile">
          <strong>Decide on pending items</strong>
          <span>Approve, ask a follow-up question, or reject.</span>
        </Link>
        <Link href="/outcomes" className="action-tile">
          <strong>Browse all requests</strong>
          <span>See every case, emails, and progress.</span>
        </Link>
        <Link href="/email" className="action-tile">
          <strong>Email intake</strong>
          <span>Check the address people mail into.</span>
        </Link>
        <Link href="/tasks" className="action-tile">
          <strong>Team tasks</strong>
          <span>Work assigned to operators.</span>
        </Link>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Recent requests</h2>
          <Link href="/outcomes" className="btn ghost">
            See all
          </Link>
        </div>
        <div className="toolbar">
          <input
            className="search"
            placeholder="Search by person, case number, or type…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {filtered.length === 0 ? (
          <div className="empty">
            <strong>No requests yet</strong>
            When someone emails the intake address, their request appears here.
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
                      {(o.title || "").slice(0, 48)}
                      {(o.title || "").length > 48 ? "…" : ""}
                    </div>
                  </td>
                  <td>
                    <span className="badge">{requestType(o)}</span>
                  </td>
                  <td className="muted">{o.department || "—"}</td>
                  <td>{o.requester_email}</td>
                  <td>
                    <span className={`badge ${priorityTone(o.priority)}`}>{friendlyPriority(o.priority)}</span>
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
