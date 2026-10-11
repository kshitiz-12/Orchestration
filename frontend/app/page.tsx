"use client";

import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import { friendlyPriority, friendlyStatus, priorityTone, requestType } from "@/lib/labels";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

export default function HomePage() {
  const [kpis, setKpis] = useState<any>(null);
  const [setup, setSetup] = useState<any>(null);
  const [outcomes, setOutcomes] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [k, o, s] = await Promise.all([
        api("/dashboard/kpis"),
        api("/outcomes?limit=10"),
        api("/setup/status").catch(() => null),
      ]);
      setKpis(k && typeof k === "object" ? k : null);
      setOutcomes(Array.isArray(o) ? o : []);
      setSetup(s);
      setUpdatedAt(new Date());
    } catch (e: any) {
      setError(e.message || "Could not load");
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

  const waitingYou =
    kpis?.waiting_on_you != null
      ? Number(kpis.waiting_on_you)
      : Number(kpis?.human_reviews || 0) + Number(kpis?.pending_approvals || 0) + Number(kpis?.pending_confirmations || 0);
  const openCases = Number(kpis?.outcomes_active || 0);
  const pastSla = Number(kpis?.past_sla || 0);
  const awaitingReqs = Number(kpis?.awaiting_requirements || 0);

  const employees = Number(setup?.employees || 0);
  const locations = Number(setup?.locations || 0);
  const deptsPending = Array.isArray(setup?.departments_needing_setup) ? setup.departments_needing_setup.length : 0;
  const companyReady = employees > 1 && locations > 0 && deptsPending === 0;

  const nextSteps: { title: string; detail: string; href: string; tone: "warn" | "danger" | "ok" | "neutral" }[] = [];
  if (!companyReady) {
    nextSteps.push({
      title: "Finish company setup",
      detail: "Upload branches, teams, and employees so mail can be routed correctly.",
      href: "/setup",
      tone: "warn",
    });
  }
  if (waitingYou > 0) {
    nextSteps.push({
      title: `${waitingYou} item${waitingYou === 1 ? "" : "s"} need your decision`,
      detail: "Approvals or confirmations are waiting on the admin team.",
      href: "/reviews",
      tone: "warn",
    });
  }
  if (pastSla > 0) {
    nextSteps.push({
      title: `${pastSla} request${pastSla === 1 ? "" : "s"} past due`,
      detail: "Teams missed the agreed time — follow up from the request.",
      href: "/outcomes",
      tone: "danger",
    });
  }
  if (awaitingReqs > 0) {
    nextSteps.push({
      title: `${awaitingReqs} waiting on the employee`,
      detail: "We already asked for the missing details by email.",
      href: "/outcomes",
      tone: "neutral",
    });
  }
  if (nextSteps.length === 0 && openCases > 0) {
    nextSteps.push({
      title: "Everything is on track",
      detail: `${openCases} open request${openCases === 1 ? "" : "s"} moving with the teams.`,
      href: "/outcomes",
      tone: "ok",
    });
  }
  if (nextSteps.length === 0) {
    nextSteps.push({
      title: "No open requests",
      detail: "When employees email the company inbox, new work shows up here.",
      href: "/email",
      tone: "neutral",
    });
  }

  return (
    <AppShell
      title="Overview"
      subtitle="What needs attention across your offices — and whether the company is ready for employee mail."
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
        <div className="panel" style={{ marginBottom: "1rem", borderColor: "#f0b4ae" }}>
          <strong style={{ color: "var(--danger)" }}>Couldn&apos;t load</strong>
          <p className="muted" style={{ margin: "0.35rem 0 0" }}>{error}</p>
          <button className="btn secondary" style={{ marginTop: "0.75rem" }} onClick={load}>
            Try again
          </button>
        </div>
      )}

      {!companyReady && (
        <div className="setup-hero">
          <div>
            <h2>Get your company ready</h2>
            <p>
              Upload one Excel file with offices, teams, and employees. Until that&apos;s done,
              only listed employees get replies — and teams need real mailboxes to receive work.
            </p>
          </div>
          <div className="setup-steps">
            <span className={`setup-step ${locations > 0 ? "done" : "warn"}`}>
              {locations > 0 ? "Offices added" : "Add offices"}
            </span>
            <span className={`setup-step ${deptsPending === 0 && setup ? "done" : "warn"}`}>
              {deptsPending === 0 && setup ? "Teams ready" : `${deptsPending || "—"} teams need email`}
            </span>
            <span className={`setup-step ${employees > 1 ? "done" : "warn"}`}>
              {employees > 1 ? `${employees} people` : "Add employees"}
            </span>
          </div>
          <div className="row">
            <Link href="/setup" className="btn accent">
              Open company data
            </Link>
            <Link href="/email" className="btn secondary">
              Check mail inbox
            </Link>
          </div>
        </div>
      )}

      <div className="panel" style={{ marginBottom: "1.15rem" }}>
        <div className="panel-head">
          <h2>Do this next</h2>
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
          <div className="value">{openCases || "0"}</div>
          <div className="hint">Still being handled</div>
        </Link>
        <Link href="/reviews" className="kpi clickable">
          <div className="label">Need your decision</div>
          <div className="value">{waitingYou || "0"}</div>
          <div className="hint">Approvals & confirmations</div>
        </Link>
        <Link href="/outcomes" className="kpi clickable">
          <div className="label">Past due</div>
          <div className="value">{pastSla || "0"}</div>
          <div className="hint">Missed team deadline</div>
        </Link>
        <Link href="/setup" className="kpi clickable">
          <div className="label">Employees loaded</div>
          <div className="value">{employees || "0"}</div>
          <div className="hint">{locations || 0} offices on file</div>
        </Link>
      </div>

      <div className="grid actions">
        <Link href="/setup" className="action-tile">
          <strong>Upload company Excel</strong>
          <span>Branches, teams, and people in one file.</span>
        </Link>
        <Link href="/outcomes" className="action-tile">
          <strong>Browse requests</strong>
          <span>See status, who is waiting, and history.</span>
        </Link>
        <Link href="/email" className="action-tile">
          <strong>Employee mail address</strong>
          <span>The inbox staff should write to.</span>
        </Link>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Recent requests</h2>
          <Link href="/outcomes" className="btn ghost">
            See all
          </Link>
        </div>
        {outcomes.length === 0 ? (
          <div className="empty">
            <strong>No requests yet</strong>
            After company data is loaded, employee emails to the intake address appear here.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Case</th>
                <th>Type</th>
                <th>Team</th>
                <th>From</th>
                <th>Priority</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {outcomes.map((o) => (
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
