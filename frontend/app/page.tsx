"use client";

import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/Status";
import { readLocalUpload, UploadMeter } from "@/components/UploadMeter";
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
  const [localUpload, setLocalUpload] = useState<ReturnType<typeof readLocalUpload>>(null);

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
      setLocalUpload(s?.excel_upload ? null : readLocalUpload());
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
  const dataLoaded = employees > 1 && locations > 0;
  const companyReady = dataLoaded && deptsPending === 0;

  const nextSteps: { title: string; detail: string; href: string; tone: "warn" | "danger" | "ok" | "neutral" }[] = [];
  if (!dataLoaded) {
    nextSteps.push({
      title: "Upload company Excel",
      detail: "Add offices, teams, and employees so mail can be routed correctly.",
      href: "/setup",
      tone: "warn",
    });
  } else if (deptsPending > 0) {
    nextSteps.push({
      title: `${deptsPending} teams still need a work email`,
      detail: "Until then, their work orders go to the main admin mailbox.",
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

      <div className="dash">
        <div className="metric-bar">
          <Link href="/outcomes" className="metric">
            <span>Open</span>
            <strong>{openCases}</strong>
            <em>Still with the teams</em>
          </Link>
          <Link href="/reviews" className="metric">
            <span>Your decision</span>
            <strong>{waitingYou}</strong>
            <em>Approvals and confirmations</em>
          </Link>
          <Link href="/outcomes" className={`metric ${pastSla > 0 ? "hot" : ""}`}>
            <span>Past due</span>
            <strong>{pastSla}</strong>
            <em>Missed the agreed time</em>
          </Link>
          <Link href="/setup" className="metric">
            <span>People</span>
            <strong>{employees}</strong>
            <em>{locations} offices on file</em>
          </Link>
        </div>

        <div className="dash-split">
          <section className="panel dash-work">
            <div className="panel-head">
              <h2>Requests</h2>
              <Link href="/outcomes" className="btn ghost">
                See all
              </Link>
            </div>
            {nextSteps.length > 0 && (
              <div className="attn-list">
                {nextSteps.map((step) => (
                  <Link key={step.title} href={step.href} className={`attn tone-${step.tone}`}>
                    <strong>{step.title}</strong>
                    <span>{step.detail}</span>
                  </Link>
                ))}
              </div>
            )}
            {outcomes.length === 0 ? (
              <div className="empty">
                <strong>No requests yet</strong>
                Employee mail shows up here after company data is loaded.
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
          </section>

          <aside className="dash-rail">
            <div className="panel">
              <h2>{companyReady ? "Company is ready" : "Company setup"}</h2>
              <p className="muted dash-note">
                {dataLoaded
                  ? "Offices and people are on file. Teams without a real mailbox still send work to the admin inbox."
                  : "Load offices, teams, and employees so employee mail can be routed."}
              </p>
              <div className="ready-list">
                <div className="ready-row">
                  <span>Offices</span>
                  <b className={locations > 0 ? "ok" : ""}>{locations > 0 ? locations : "None yet"}</b>
                </div>
                <div className="ready-row">
                  <span>Teams needing email</span>
                  <b className={deptsPending === 0 && setup ? "ok" : ""}>{setup ? deptsPending : "—"}</b>
                </div>
                <div className="ready-row">
                  <span>People</span>
                  <b className={employees > 1 ? "ok" : ""}>{employees}</b>
                </div>
              </div>
              <div className="row">
                <Link href="/setup" className="btn accent">
                  {dataLoaded ? "Edit company data" : "Upload Excel"}
                </Link>
                <Link href="/email" className="btn secondary">
                  Mail inbox
                </Link>
              </div>
            </div>
            <div className="panel">
              <UploadMeter source={setup?.excel_upload || localUpload} />
            </div>
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
