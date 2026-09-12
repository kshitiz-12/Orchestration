"use client";

import { AppShell } from "@/components/AppShell";
import { ReadinessBar, StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import { friendlyStatus, friendlyType } from "@/lib/labels";
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

  const waitingYou = Number(kpis?.human_reviews || 0) + Number(kpis?.pending_approvals || 0);
  const late = Number(kpis?.overdue_tasks || 0);
  const problems = Number(kpis?.failures || 0);
  const openCases = Number(kpis?.outcomes_active || 0);
  const needsAttention = Number(kpis?.at_risk || 0);

  const nextSteps: { title: string; detail: string; href: string; tone: "warn" | "danger" | "ok" | "neutral" }[] = [];
  if (waitingYou > 0) {
    nextSteps.push({
      title: `${waitingYou} item${waitingYou === 1 ? "" : "s"} waiting for your decision`,
      detail: "Open these first — the system paused until someone confirms.",
      href: "/reviews",
      tone: "warn",
    });
  }
  if (late > 0) {
    nextSteps.push({
      title: `${late} late task${late === 1 ? "" : "s"}`,
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
          <div className="hint">Approve or ask for more info</div>
        </Link>
        <Link href="/tasks" className="kpi clickable">
          <div className="label">Late work</div>
          <div className="value">{late || "—"}</div>
          <div className="hint">Tasks past their due time</div>
        </Link>
      </div>

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
                <th>What is it?</th>
                <th>From</th>
                <th>Status</th>
                <th>Progress</th>
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
                    <span className="badge">{friendlyType(o.template_code)}</span>
                  </td>
                  <td>{o.requester_email}</td>
                  <td>
                    <StatusBadge status={friendlyStatus(o.status)} />
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
