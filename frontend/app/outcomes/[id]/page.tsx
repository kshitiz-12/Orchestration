"use client";

import { AppShell } from "@/components/AppShell";
import { ReadinessBar, StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function OutcomeDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [data, setData] = useState<any>(null);
  const [msg, setMsg] = useState("");

  function load() {
    api(`/outcomes/${id}`).then(setData).catch((e) => setMsg(e.message));
  }

  useEffect(() => {
    load();
  }, [id]);

  if (!data) {
    return (
      <AppShell title="Outcome" subtitle={msg || "Loading case details…"}>
        <div className="panel empty">
          <strong>{msg ? "Could not load" : "Loading…"}</strong>
          {msg || "Fetching email, AI decision, tasks, and audit trail."}
        </div>
      </AppShell>
    );
  }

  const {
    outcome,
    email,
    ai_decision,
    requirements,
    tasks,
    exceptions,
    evidence,
    communications,
    audit,
    vendor_issues,
    approvals,
  } = data;

  return (
    <AppShell
      title={outcome.case_reference}
      subtitle={outcome.title}
      actions={
        <>
          <StatusBadge status={outcome.status} />
          <button
            className="btn accent"
            onClick={async () => {
              try {
                await api(`/outcomes/${id}/close`, { method: "POST" });
                setMsg("Closed");
                load();
              } catch (e: any) {
                setMsg(e.message);
              }
            }}
          >
            Verify & close
          </button>
          <button
            className="btn secondary"
            onClick={async () => {
              try {
                const res = await api(`/outcomes/${id}/resend-clarification`, { method: "POST" });
                setMsg(res.delivered ? "Clarification emailed" : "Saved but not delivered");
                load();
              } catch (e: any) {
                setMsg(e.message);
              }
            }}
          >
            Resend clarification
          </button>
        </>
      }
    >
      {msg && <p className="badge danger">{msg}</p>}
      <div className="grid kpis" style={{ marginBottom: "1.25rem" }}>
        <div className="kpi">
          <div className="label">Readiness</div>
          <div className="value" style={{ fontSize: "1.4rem" }}>
            <ReadinessBar value={outcome.readiness_pct} />
          </div>
        </div>
        <div className="kpi">
          <div className="label">Requester</div>
          <div className="value" style={{ fontSize: "0.95rem", marginTop: "0.5rem" }}>
            {outcome.requester_email}
          </div>
        </div>
        <div className="kpi">
          <div className="label">Template</div>
          <div className="value" style={{ fontSize: "0.95rem", marginTop: "0.5rem" }}>
            {outcome.template_code}
          </div>
        </div>
      </div>
      <div className="cols-2">
        <div className="stack">
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Original email</h2>
            {email ? (
              <>
                <div className="muted">
                  {email.sender} · {email.subject}
                </div>
                <div className="pre">{email.body_text}</div>
              </>
            ) : (
              <p className="muted">No email linked</p>
            )}
          </div>
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>AI interpretation</h2>
            {ai_decision ? (
              <>
                <p>
                  Confidence <strong>{ai_decision.confidence}</strong> · route{" "}
                  <span className="badge accent">{ai_decision.route}</span>
                </p>
                <div className="pre">{JSON.stringify(ai_decision.output, null, 2)}</div>
              </>
            ) : (
              <p className="muted">No AI decision</p>
            )}
          </div>
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Communications</h2>
            {(communications || []).map((c: any) => (
              <div key={c.message_id} style={{ marginBottom: "0.75rem" }}>
                <div className="badge">{c.communication_type}</div>
                <div className="mono">{c.subject}</div>
                <div className="pre">{c.body}</div>
              </div>
            ))}
            {(communications || []).length === 0 && <p className="muted">None yet</p>}
          </div>
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Audit timeline</h2>
            <table>
              <tbody>
                {(audit || []).map((a: any) => (
                  <tr key={a.audit_id}>
                    <td className="mono">{new Date(a.timestamp).toLocaleString()}</td>
                    <td>{a.action}</td>
                    <td className="muted">{a.actor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="stack">
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Requirements</h2>
            <table>
              <tbody>
                {(requirements || []).map((r: any) => (
                  <tr key={r.requirement_id}>
                    <td>{r.title}</td>
                    <td>
                      <StatusBadge status={r.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Tasks & dependencies</h2>
            <table>
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Owner</th>
                  <th>Status</th>
                  <th>Deps</th>
                </tr>
              </thead>
              <tbody>
                {(tasks || []).map((t: any) => (
                  <tr key={t.task_id}>
                    <td>
                      {t.title}
                      {t.is_blocked && <span className="badge warn"> BLOCKED</span>}
                    </td>
                    <td>{t.owner_role}</td>
                    <td>
                      <StatusBadge status={t.status} />
                    </td>
                    <td className="mono">{(t.depends_on_task_codes || []).join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Exceptions / risks</h2>
            {(exceptions || []).map((e: any) => (
              <div key={e.exception_id} style={{ marginBottom: "0.5rem" }}>
                <span className="badge danger">{e.severity}</span> {e.title}
                <div className="muted">{e.description}</div>
              </div>
            ))}
            {(vendor_issues || []).map((v: any) => (
              <div key={v.issue_id} className="muted">
                [{v.workstream}] {v.issue_type} — {v.allegation_status}
              </div>
            ))}
            {(exceptions || []).length === 0 && (vendor_issues || []).length === 0 && (
              <p className="muted">None</p>
            )}
          </div>
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Approvals</h2>
            {(approvals || []).map((a: any) => (
              <div key={a.approval_id} className="row" style={{ marginBottom: "0.5rem" }}>
                <span>
                  {a.approval_type} · {a.decision}
                </span>
                {a.decision === "PENDING" && (
                  <button
                    className="btn secondary"
                    onClick={async () => {
                      await api(`/approvals/${a.approval_id}/decide`, {
                        method: "POST",
                        body: JSON.stringify({ decision: "APPROVED", reason: "Prototype approval" }),
                      });
                      load();
                    }}
                  >
                    Approve
                  </button>
                )}
              </div>
            ))}
            {(approvals || []).length === 0 && <p className="muted">None</p>}
          </div>
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Evidence</h2>
            {(evidence || []).length === 0 && <p className="muted">None yet</p>}
            {(evidence || []).map((e: any) => (
              <div key={e.evidence_id}>
                {e.evidence_type} · {e.status}
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
