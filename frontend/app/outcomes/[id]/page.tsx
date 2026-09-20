"use client";

import { AppShell } from "@/components/AppShell";
import { ReadinessBar, StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import { friendlyAudit, friendlyStatus, friendlyType } from "@/lib/labels";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

const CONFIRMED_PROV = new Set(["extracted", "user_confirmed", "candidate_heuristic"]);
const ASSUMED_PROV = new Set(["inferred_policy", "system", "master"]);

function prettyField(field: string) {
  return String(field || "").replaceAll("_", " ");
}

function isPlaceholder(value: unknown) {
  const t = String(value ?? "").trim().toLowerCase();
  return ["to be confirmed", "tbd", "unknown", "unconfirmed", "not confirmed", "pending", "n/a", "na"].includes(
    t,
  );
}

function isConfirmedRow(r: any) {
  if (!r) return false;
  const prov = String(r.provenance || "").toLowerCase();
  if (r.value == null || r.value === "" || isPlaceholder(r.value)) return false;
  if (CONFIRMED_PROV.has(prov)) return true;
  if (ASSUMED_PROV.has(prov) || r.status === "assumed") return false;
  return r.status === "stated";
}

function FieldTable({ rows }: { rows: any[] }) {
  return (
    <table>
      <tbody>
        {rows.map((r, i) => (
          <tr key={`${r.field || r.question || i}`}>
            <td className="muted" style={{ textTransform: "capitalize", width: "28%" }}>
              {prettyField(r.field || "item")}
            </td>
            <td>
              {r.question && (r.status === "blocking" || r.note === "still needed")
                ? r.question
                : String(r.value ?? "not answered")}
            </td>
            <td className="muted" style={{ width: "22%" }}>
              {prettyField(r.note || r.provenance || r.status || "")}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function OutcomeDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [data, setData] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const [msgTone, setMsgTone] = useState<"ok" | "danger">("ok");
  const [busy, setBusy] = useState("");
  const [roomName, setRoomName] = useState("");
  const [confirmNote, setConfirmNote] = useState("");
  const [overrideJson, setOverrideJson] = useState('{\n  "attendees": 12\n}');
  const [overrideNote, setOverrideNote] = useState("");
  const [reopenReason, setReopenReason] = useState("");

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
    field_contract,
  } = data;

  const facts = { ...(conversation?.facts || {}), ...(outcome.facts || {}) };
  delete facts.issues;
  const factEntries = Object.entries(facts).filter(([, v]) => v !== null && v !== "" && typeof v !== "object");
  const contract = field_contract || facts.field_contract || {};
  const understoodRows = Array.isArray(contract.understood) ? contract.understood : [];
  const assumedRows = Array.isArray(contract.assumed) ? contract.assumed : [];
  const missingRows = Array.isArray(contract.missing) ? contract.missing : [];
  const stillNeeded =
    missingRows.length > 0
      ? missingRows
      : Array.isArray(conversation?.missing_information)
        ? conversation.missing_information
        : [];

  const confirmedRows: any[] = understoodRows.filter(isConfirmedRow);
  const seenFields = new Set(confirmedRows.map((r: any) => r.field).filter(Boolean));
  const lowerRows: any[] = [];
  const pushLower = (r: any, note: string) => {
    if (!r) return;
    if (r.field && seenFields.has(r.field)) return;
    if (r.field) seenFields.add(r.field);
    lowerRows.push({ ...r, note });
  };
  understoodRows.filter((r: any) => !isConfirmedRow(r)).forEach((r: any) => pushLower(r, "not confirmed"));
  assumedRows.forEach((r: any) => pushLower(r, "assumed"));
  stillNeeded.forEach((r: any) =>
    pushLower({ ...r, value: r.question || r.value || "not answered", status: "blocking" }, "still needed"),
  );
  Object.values(contract.fields || {}).forEach((r: any) => {
    if (!r || r.status !== "unknown") return;
    if (["duration_hours", "end_time", "primary_office", "external_visitors_indicated"].includes(r.field)) return;
    pushLower({ ...r, value: r.value ?? "not answered" }, "not answered");
  });
  if (confirmedRows.length === 0 && factEntries.length > 0 && understoodRows.length === 0) {
    factEntries.forEach(([k, v]) => confirmedRows.push({ field: k, value: v, status: "stated", provenance: "extracted" }));
  }

  const interpretationPath =
    facts.interpretation_path ||
    ai_decision?.model ||
    (String(ai_decision?.rationale || "").includes("heuristic") ? "heuristic fallback" : null);

  const lastOutbound = facts.last_outbound && typeof facts.last_outbound === "object" ? facts.last_outbound : null;

  const needsOpsConfirm =
    outcome.template_code === "MEETING_ROOM" &&
    !facts.booked_room &&
    (facts.needs_ops === true ||
      facts.pending_confirmation === true ||
      (tasks || []).some((t: any) => t.code === "RESERVE_ROOM" && !["VERIFIED", "CLOSED"].includes(t.status)));

  const stageLabel = String(facts.orchestration_stage || contract.stage || "").replaceAll("_", " ") || "—";
  const requesterName = facts.requester_display_name || outcome.requester_email;
  const canReopen = ["CLOSED", "VERIFIED", "ADMINISTRATIVELY_CLOSED"].includes(outcome.status);

  return (
    <AppShell
      title={outcome.case_reference}
      subtitle={outcome.title || friendlyType(outcome.template_code)}
      actions={
        <>
          <StatusBadge status={friendlyStatus(outcome.status)} />
          {needsOpsConfirm && (
            <button
              className="btn accent"
              disabled={busy === "confirm"}
              onClick={async () => {
                setBusy("confirm");
                try {
                  await api(`/outcomes/${id}/confirm-booking`, {
                    method: "POST",
                    body: JSON.stringify({
                      room_name: roomName || undefined,
                      note: confirmNote || undefined,
                    }),
                  });
                  setMsgTone("ok");
                  setMsg("Booking confirmed — confirmation email sent to the requester.");
                  load();
                } catch (e: any) {
                  setMsgTone("danger");
                  setMsg(e.message);
                } finally {
                  setBusy("");
                }
              }}
            >
              Confirm booking & notify
            </button>
          )}
          <button
            className="btn secondary"
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
                setMsgTone(res.delivered ? "ok" : res.suppressed ? "ok" : "danger");
                setMsg(
                  res.suppressed
                    ? `Clarification suppressed (${res.suppress_reason || "duplicate"}).`
                    : res.delivered
                      ? "Follow-up email sent — only remaining gaps asked."
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
          {canReopen && (
            <button
              className="btn secondary"
              disabled={busy === "reopen"}
              onClick={async () => {
                setBusy("reopen");
                try {
                  await api(`/outcomes/${id}/reopen`, {
                    method: "POST",
                    body: JSON.stringify({ reason: reopenReason || "Operator reopen" }),
                  });
                  setMsgTone("ok");
                  setMsg("Request reopened.");
                  load();
                } catch (e: any) {
                  setMsgTone("danger");
                  setMsg(e.message);
                } finally {
                  setBusy("");
                }
              }}
            >
              Reopen
            </button>
          )}
        </>
      }
    >
      {msg && <p className={`badge ${msgTone === "ok" ? "ok" : "danger"}`}>{msg}</p>}

      {facts.pending_confirmation && facts.proposed_room && typeof facts.proposed_room === "object" && (
        <div className="panel" style={{ marginBottom: "1.25rem" }}>
          <h2 style={{ marginBottom: "0.5rem" }}>Awaiting requester confirmation</h2>
          <p style={{ marginTop: 0 }}>
            Proposed {(facts.proposed_room as any).name}. Requester was asked to reply{" "}
            <strong>confirm</strong> (or you can confirm here for them).
          </p>
        </div>
      )}

      <div className="panel" style={{ marginBottom: "1.25rem" }}>
        <div className="field-split-upper">
          <h2 style={{ marginBottom: "0.5rem" }}>Confirmed / extracted</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            Stated in the request or confirmed by the requester.
          </p>
          {confirmedRows.length > 0 ? (
            <FieldTable rows={confirmedRows} />
          ) : (
            <p className="muted">Nothing confirmed yet.</p>
          )}
        </div>
        <div className="field-split-lower">
          <h2 style={{ marginBottom: "0.5rem" }}>Not confirmed / still needed</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            Unanswered questions, assumed defaults, and fields not yet confirmed.
          </p>
          {lowerRows.length > 0 ? (
            <FieldTable rows={lowerRows} />
          ) : (
            <p className="muted">No open fields.</p>
          )}
        </div>
      </div>

      {outcome.template_code === "MEETING_ROOM" && (
        <div className="panel" style={{ marginBottom: "1.25rem" }}>
          <h2 style={{ marginBottom: "0.5rem" }}>Meeting outcome stages</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            Stage: {stageLabel} · Ops: {String(facts.operational_status || "ACTIVE")} · Finance:{" "}
            {String(facts.financial_status || "NOT_STARTED")} · Readiness: {outcome.readiness_pct ?? 0}%
            {facts.auto_booked_low_risk ? " · Low-risk auto-book" : ""}
          </p>
          {interpretationPath && (
            <p style={{ marginTop: 0 }}>
              AI path: <strong>{String(interpretationPath)}</strong>
              {String(interpretationPath).includes("heuristic")
                ? " — Gemini unavailable; heuristic filled blanks where possible."
                : " — Gemini led; heuristic only filled empty fields."}
            </p>
          )}
          {lastOutbound && (
            <p className="muted" style={{ marginTop: 0 }}>
              Last outbound: {String((lastOutbound as any).status)}
              {(lastOutbound as any).reason ? ` — ${(lastOutbound as any).reason}` : ""}
              {(lastOutbound as any).subject ? ` · ${(lastOutbound as any).subject}` : ""}
            </p>
          )}
          {stillNeeded.length > 0 && (
            <p style={{ marginTop: 0 }}>
              Incomplete — waiting on:{" "}
              {stillNeeded.map((m: any) => m.field || m.question).filter(Boolean).join(", ")}. No room
              booked until mandatory facts are provided.
            </p>
          )}
          {Array.isArray(facts.no_resource_alternatives) && facts.no_resource_alternatives.length > 0 && (
            <div style={{ marginTop: "0.75rem" }}>
              <div className="muted" style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.35rem" }}>
                NO_RESOURCE alternatives
              </div>
              <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
                {(facts.no_resource_alternatives as { code?: string; label?: string }[]).map((a, i) => (
                  <li key={i}>
                    <strong>{a.code}</strong> — {a.label}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {Array.isArray(facts.decision_trace) && facts.decision_trace.length > 0 && (
            <div style={{ marginTop: "0.75rem" }}>
              <div className="muted" style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.35rem" }}>
                Decision trace (latest {Math.min(8, (facts.decision_trace as any[]).length)})
              </div>
              <ul className="muted" style={{ margin: 0, paddingLeft: "1.1rem", fontSize: "0.85rem" }}>
                {[...(facts.decision_trace as any[])].slice(-8).reverse().map((d, i) => (
                  <li key={i}>
                    {d.kind}
                    {d.policy_version ? ` · policy ${d.policy_version}` : ""}
                    {d.room ? ` · ${d.room}` : ""}
                    {d.stage ? ` · ${d.stage}` : ""}
                    {Array.isArray(d.gaps) && d.gaps.length ? ` · gaps: ${d.gaps.join(", ")}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {facts.modules_active && typeof facts.modules_active === "object" && (
            <p className="muted">
              Modules:{" "}
              {Object.entries(facts.modules_active as Record<string, boolean>)
                .filter(([, on]) => on)
                .map(([k]) => k)
                .join(", ") || "none"}
              {facts.policy_version ? ` · policy ${facts.policy_version}` : ""}
            </p>
          )}
          {Array.isArray(facts.policy_assumptions) && facts.policy_assumptions.length > 0 && (
            <ul style={{ margin: "0.5rem 0", paddingLeft: "1.1rem" }}>
              {(facts.policy_assumptions as { message?: string; code?: string }[]).map((a, i) => (
                <li key={i}>{a.message || a.code}</li>
              ))}
            </ul>
          )}
          {Array.isArray(facts.execution_plan) && facts.execution_plan.length > 0 && (
            <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.1rem" }}>
              {(facts.execution_plan as string[]).map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ul>
          )}
          {facts.booked_room && typeof facts.booked_room === "object" && (
            <p style={{ marginBottom: 0 }}>
              Room: {(facts.booked_room as any).name}
              {facts.hold_start ? ` · Hold: ${facts.hold_start} – ${facts.hold_end || ""}` : ""}
            </p>
          )}
          {Array.isArray(facts.visitors) && facts.visitors.length > 0 && (
            <p className="muted">Visitors prepared: {(facts.visitors as any[]).length}</p>
          )}
          {Array.isArray(facts.parking_allocation) && (
            <p className="muted">Parking spaces: {(facts.parking_allocation as any[]).length}</p>
          )}
          {facts.catering_quote && typeof facts.catering_quote === "object" && (
            <p className="muted">
              Catering quote: INR {(facts.catering_quote as any).amount_ex_tax} (
              {(facts.catering_quote as any).vendor})
            </p>
          )}
          {facts.operational_status === "CLOSED" && facts.financial_status !== "CLOSED" && (
            <button
              className="btn secondary"
              style={{ marginTop: "0.75rem" }}
              disabled={busy === "fin"}
              onClick={async () => {
                setBusy("fin");
                try {
                  await api(`/outcomes/${id}/close-financial`, { method: "POST" });
                  setMsgTone("ok");
                  setMsg("Financial close completed.");
                  load();
                } catch (e: any) {
                  setMsgTone("danger");
                  setMsg(e.message);
                } finally {
                  setBusy("");
                }
              }}
            >
              Close financials
            </button>
          )}
        </div>
      )}

      {needsOpsConfirm && (
        <div className="panel" style={{ marginBottom: "1.25rem" }}>
          <h2 style={{ marginBottom: "0.5rem" }}>Confirm this booking</h2>
          <p style={{ marginTop: 0 }}>
            {facts.pending_confirmation
              ? "Requester was offered a room. Confirm for them if needed, or wait for their reply."
              : "The requester was told you will confirm soon. Choose a room (optional) and click"}{" "}
            {!facts.pending_confirmation && (
              <>
                <strong>Confirm booking & notify</strong> — they get a confirmation email and this case closes.
              </>
            )}
          </p>
          <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" }}>
            <label style={{ display: "grid", gap: "0.25rem", minWidth: "220px" }}>
              <span className="muted" style={{ fontSize: "0.8rem" }}>
                Room name (optional)
              </span>
              <input
                className="input"
                placeholder="e.g. Boardroom A"
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
              />
            </label>
            <label style={{ display: "grid", gap: "0.25rem", flex: 1, minWidth: "220px" }}>
              <span className="muted" style={{ fontSize: "0.8rem" }}>
                Note to requester (optional)
              </span>
              <input
                className="input"
                placeholder="e.g. Catering arranged for 10am"
                value={confirmNote}
                onChange={(e) => setConfirmNote(e.target.value)}
              />
            </label>
          </div>
        </div>
      )}

      {facts.booked_room && typeof facts.booked_room === "object" && (
        <div className="panel" style={{ marginBottom: "1.25rem" }}>
          <h2 style={{ marginBottom: "0.5rem" }}>Booking confirmed</h2>
          <p style={{ marginTop: 0 }}>
            {(facts.booked_room as any).name} · assigned to {outcome.requester_email}
          </p>
        </div>
      )}

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
            {requesterName}
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
            <h2 style={{ marginBottom: "0.75rem" }}>Summary</h2>
            <p style={{ marginTop: 0 }}>
              {ai_decision?.output?.summary || outcome.summary || "The system is still gathering details."}
            </p>
          </div>

          {outcome.template_code === "MEETING_ROOM" && (
            <div className="panel">
              <h2 style={{ marginBottom: "0.75rem" }}>Operator override</h2>
              <p className="muted" style={{ marginTop: 0 }}>
                Set facts with <strong>user_confirmed</strong> provenance. JSON object of fields to set.
              </p>
              <textarea
                className="input"
                rows={5}
                value={overrideJson}
                onChange={(e) => setOverrideJson(e.target.value)}
                style={{ width: "100%", fontFamily: "ui-monospace, monospace", fontSize: "0.85rem" }}
              />
              <input
                className="input"
                style={{ marginTop: "0.5rem", width: "100%" }}
                placeholder="Note (optional)"
                value={overrideNote}
                onChange={(e) => setOverrideNote(e.target.value)}
              />
              {canReopen && (
                <input
                  className="input"
                  style={{ marginTop: "0.5rem", width: "100%" }}
                  placeholder="Reopen reason (optional)"
                  value={reopenReason}
                  onChange={(e) => setReopenReason(e.target.value)}
                />
              )}
              <button
                className="btn secondary"
                style={{ marginTop: "0.75rem" }}
                disabled={busy === "override"}
                onClick={async () => {
                  setBusy("override");
                  try {
                    const parsed = JSON.parse(overrideJson);
                    await api(`/outcomes/${id}/override-facts`, {
                      method: "POST",
                      body: JSON.stringify({
                        set: parsed,
                        note: overrideNote || undefined,
                        re_orchestrate: true,
                      }),
                    });
                    setMsgTone("ok");
                    setMsg("Facts overridden and case re-checked.");
                    load();
                  } catch (e: any) {
                    setMsgTone("danger");
                    setMsg(e.message || "Invalid override JSON");
                  } finally {
                    setBusy("");
                  }
                }}
              >
                Apply override
              </button>
            </div>
          )}

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
