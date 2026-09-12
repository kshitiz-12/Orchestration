"use client";

import { AppShell } from "@/components/AppShell";
import { ReadinessBar, StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import { friendlyAudit, friendlyStatus, friendlyType } from "@/lib/labels";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function OutcomeDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [data, setData] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const [msgTone, setMsgTone] = useState<"ok" | "danger">("ok");
  const [busy, setBusy] = useState("");

  function load() {
    api(`/outcomes/${id}`)
      .then(setData)
      .catch((e) => {
        setMsgTone("danger");
        setMsg(e.message);
      });
  }

  useEffect(() => {
    load();
  }, [id]);

  if (!data) {
    return (
      <AppShell title="Request" subtitle={msg || "Loading…"}>
        <div className="panel empty">
          <strong>{msg ? "Could not load" : "Loading…"}</strong>
          {msg || "Fetching this request."}
        </div>
      </AppShell>
    );
  }

  const {
    outcome,
    email,
    thread_emails,
    ai_decision,
    requirements,
    tasks,
    exceptions,
    evidence,
    communications,
    audit,
    vendor_issues,
    approvals,
    conversation,
  } = data;

  const facts = { ...(conversation?.facts || {}), ...(outcome.facts || {}) };
  delete facts.issues;
  const factEntries = Object.entries(facts).filter(([, v]) => v !== null && v !== "" && typeof v !== "object");
  const missing = Array.isArray(conversation?.missing_information)
    ? conversation.missing_information
    : conversation?.missing_information
      ? [conversation.missing_information]
      : [];

  const understood =
    ai_decision?.output?.summary ||
    outcome.summary ||
    "The system is still gathering details.";

  return (
    <AppShell
      title={outcome.case_reference}
      subtitle={outcome.title || friendlyType(outcome.template_code)}
      actions={
        <>
          <StatusBadge status={friendlyStatus(outcome.status)} />
          <button
            className="btn accent"
            disabled={busy === "close"}
            onClick={async () => {
              setBusy("close");
              try {
                await api(`/outcomes/${id}/close`, { method: "POST" });
                setMsgTone("ok");
                setMsg("Request marked done.");
                load();
              } catch (e: any) {
                setMsgTone("danger");
                setMsg(e.message);
              } finally {
                setBusy("");
              }
            }}
          >
            Mark as done
          </button>
          <button
            className="btn secondary"
            disabled={busy === "resend"}
            onClick={async () => {
              setBusy("resend");
              try {
                const res = await api(`/outcomes/${id}/resend-clarification`, { method: "POST" });
                setMsgTone(res.delivered ? "ok" : "danger");
                setMsg(
                  res.delivered
                    ? "Follow-up email sent to the requester."
                    : "Saved, but the email could not be delivered."
                );
                load();
              } catch (e: any) {
                setMsgTone("danger");
                setMsg(e.message);
              } finally {
                setBusy("");
              }
            }}
          >
            Ask for more info again
          </button>
        </>
      }
    >
      {msg && <p className={`badge ${msgTone === "ok" ? "ok" : "danger"}`}>{msg}</p>}

      <div className="grid kpis" style={{ marginBottom: "1.25rem" }}>
        <div className="kpi">
          <div className="label">Progress</div>
          <div className="value" style={{ fontSize: "1.4rem" }}>
            <ReadinessBar value={outcome.readiness_pct} />
          </div>
        </div>
        <div className="kpi">
          <div className="label">From</div>
          <div className="value" style={{ fontSize: "0.95rem", marginTop: "0.5rem" }}>
            {outcome.requester_email}
          </div>
        </div>
        <div className="kpi">
          <div className="label">Request type</div>
          <div className="value" style={{ fontSize: "0.95rem", marginTop: "0.5rem" }}>
            {friendlyType(outcome.template_code)}
          </div>
        </div>
      </div>

      <div className="cols-2">
        <div className="stack">
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>What we know</h2>
            <p style={{ marginTop: 0 }}>{understood}</p>
            {factEntries.length > 0 ? (
              <table>
                <tbody>
                  {factEntries.map(([k, v]) => (
                    <tr key={k}>
                      <td className="muted" style={{ textTransform: "capitalize" }}>
                        {k.replaceAll("_", " ")}
                      </td>
                      <td>{String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="muted">No details captured yet.</p>
            )}
            {missing.length > 0 && (
              <div style={{ marginTop: "0.75rem" }}>
                <div className="muted" style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.35rem" }}>
                  Still needed
                </div>
                <ul className="muted" style={{ margin: 0, paddingLeft: "1.1rem" }}>
                  {missing.map((m: any, i: number) => (
                    <li key={i}>{m.question || m.field}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Email thread</h2>
            {(thread_emails || []).length > 0 ? (
              (thread_emails || []).map((e: any) => (
                <div key={e.event_id} style={{ marginBottom: "0.85rem" }}>
                  <div className="muted" style={{ fontSize: "0.8rem" }}>
                    {e.sender} · {new Date(e.received_at || e.created_at).toLocaleString()}
                  </div>
                  <div style={{ fontWeight: 600, margin: "0.2rem 0" }}>{e.subject}</div>
                  <div className="pre">{e.body_text}</div>
                </div>
              ))
            ) : email ? (
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
            <h2 style={{ marginBottom: "0.75rem" }}>Emails we sent</h2>
            {(communications || []).map((c: any) => (
              <div key={c.message_id} style={{ marginBottom: "0.75rem" }}>
                <div className="badge">{c.communication_type === "INFORMATION_REQUIRED" ? "Asked for details" : c.communication_type}</div>
                <div style={{ fontWeight: 600, margin: "0.35rem 0" }}>{c.subject}</div>
                <div className="pre">{c.body}</div>
              </div>
            ))}
            {(communications || []).length === 0 && <p className="muted">None yet</p>}
          </div>

          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Activity</h2>
            <table>
              <tbody>
                {(audit || []).slice(0, 30).map((a: any) => (
                  <tr key={a.audit_id}>
                    <td className="muted">{new Date(a.timestamp).toLocaleString()}</td>
                    <td>{friendlyAudit(a.action)}</td>
                    <td className="muted">{a.actor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="stack">
          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Checklist</h2>
            <table>
              <tbody>
                {(requirements || []).map((r: any) => (
                  <tr key={r.requirement_id}>
                    <td>{r.title}</td>
                    <td>
                      <StatusBadge status={friendlyStatus(r.status)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(requirements || []).length === 0 && <p className="muted">None</p>}
          </div>

          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Team tasks</h2>
            <table>
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Owner</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(tasks || []).map((t: any) => (
                  <tr key={t.task_id}>
                    <td>
                      {t.title}
                      {t.is_blocked && <span className="badge warn"> blocked</span>}
                    </td>
                    <td>{t.owner_role}</td>
                    <td>
                      <StatusBadge status={friendlyStatus(t.status)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(tasks || []).length === 0 && <p className="muted">None</p>}
          </div>

          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Issues</h2>
            {(exceptions || []).map((e: any) => (
              <div key={e.exception_id} style={{ marginBottom: "0.5rem" }}>
                <span className="badge danger">{e.severity}</span> {e.title}
                <div className="muted">{e.description}</div>
              </div>
            ))}
            {(vendor_issues || []).map((v: any) => (
              <div key={v.issue_id} className="muted">
                {v.issue_type} — {v.allegation_status}
              </div>
            ))}
            {(exceptions || []).length === 0 && (vendor_issues || []).length === 0 && (
              <p className="muted">No issues</p>
            )}
          </div>

          <div className="panel">
            <h2 style={{ marginBottom: "0.75rem" }}>Approvals</h2>
            {(approvals || []).map((a: any) => (
              <div key={a.approval_id} className="row" style={{ marginBottom: "0.5rem" }}>
                <span>
                  {a.approval_type} · {friendlyStatus(a.decision)}
                </span>
                {a.decision === "PENDING" && (
                  <button
                    className="btn secondary"
                    onClick={async () => {
                      await api(`/approvals/${a.approval_id}/decide`, {
                        method: "POST",
                        body: JSON.stringify({ decision: "APPROVED", reason: "Approved in console" }),
                      });
                      setMsgTone("ok");
                      setMsg("Approved.");
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
                {e.evidence_type} · {friendlyStatus(e.status)}
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
