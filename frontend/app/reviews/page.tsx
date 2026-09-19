"use client";

import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import Link from "next/link";
import { useEffect, useState } from "react";

function plainSummary(output: any) {
  if (!output) return "No summary yet.";
  const type = output.event_type || "Request";
  const summary = output.summary || "";
  const missing = (output.missing_information || [])
    .map((m: any) => m.question || m.field)
    .filter(Boolean);
  const parts = [`Type: ${type}`];
  if (summary) parts.push(summary);
  if (missing.length) parts.push(`Still needed: ${missing.join(" · ")}`);
  return parts.join("\n");
}

export default function ReviewsPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  function load() {
    api("/reviews")
      .then((data) => setRows(Array.isArray(data) ? data : []))
      .catch((e) => setMsg(e.message));
  }

  useEffect(() => {
    load();
  }, []);

  async function decide(reviewId: string, action: string) {
    setBusyId(reviewId);
    setMsg("");
    try {
      await api(`/reviews/${reviewId}/decide`, {
        method: "POST",
        body: JSON.stringify({ action, reason: `Decision: ${action}` }),
      });
      load();
      if (action === "ACCEPT") setMsg("Approved — the request will continue.");
      if (action === "CLARIFY") setMsg("Follow-up question sent to the requester.");
      if (action === "REJECT") setMsg("Marked as rejected.");
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function decideApproval(approvalId: string, decision: string) {
    setBusyId(approvalId);
    setMsg("");
    try {
      await api(`/approvals/${approvalId}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision, reason: `Decision: ${decision}` }),
      });
      load();
      setMsg(decision === "APPROVED" ? "Spend approved." : "Approval rejected.");
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function confirmRoom(outcomeId: string) {
    setBusyId(outcomeId);
    setMsg("");
    try {
      await api(`/outcomes/${outcomeId}/confirm-booking`, {
        method: "POST",
        body: JSON.stringify({ note: "Confirmed from Needs your decision" }),
      });
      load();
      setMsg("Room booking confirmed.");
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <AppShell
      title="Needs your decision"
      subtitle="Reviews, spend approvals, and room proposals waiting on an operator."
      actions={
        <button className="btn secondary" onClick={load}>
          Refresh
        </button>
      }
    >
      {msg && <p className="badge ok">{msg}</p>}
      <div className="stack">
        {rows.map((row) => {
          const review = row.review || (row.review_id ? row : null);
          if (row.kind === "approval" && row.approval) {
            const a = row.approval;
            const o = row.outcome || {};
            const payload = a.payload || {};
            return (
              <div className="panel" key={a.approval_id}>
                <div className="panel-head">
                  <div>
                    <h3 style={{ marginBottom: "0.35rem" }}>
                      {a.approval_type?.replaceAll("_", " ") || "Approval"} — {o.case_reference}
                    </h3>
                    <div className="chip-row">
                      <span className="badge">{o.requester_email || "unknown"}</span>
                      <StatusBadge status={a.decision} />
                    </div>
                  </div>
                </div>
                <p className="muted" style={{ marginTop: 0 }}>
                  {payload.vendor ? `${payload.vendor} · ` : ""}
                  {payload.amount_ex_tax != null
                    ? `${payload.currency || "INR"} ${payload.amount_ex_tax}`
                    : "Spend approval needed before catering can proceed."}
                </p>
                <div className="row" style={{ marginTop: "0.9rem" }}>
                  <button
                    className="btn accent"
                    disabled={busyId === a.approval_id}
                    onClick={() => decideApproval(a.approval_id, "APPROVED")}
                  >
                    Approve spend
                  </button>
                  <button
                    className="btn danger"
                    disabled={busyId === a.approval_id}
                    onClick={() => decideApproval(a.approval_id, "REJECTED")}
                  >
                    Reject
                  </button>
                  {o.outcome_id && (
                    <Link className="btn secondary" href={`/outcomes/${o.outcome_id}`}>
                      Open request
                    </Link>
                  )}
                </div>
              </div>
            );
          }

          if (row.kind === "confirm_booking" && row.outcome) {
            const o = row.outcome;
            return (
              <div className="panel" key={`confirm-${o.outcome_id}`}>
                <div className="panel-head">
                  <div>
                    <h3 style={{ marginBottom: "0.35rem" }}>
                      Confirm room — {o.case_reference}
                    </h3>
                    <div className="chip-row">
                      <span className="badge">{o.requester_email || "unknown"}</span>
                      <StatusBadge status="PENDING" />
                    </div>
                  </div>
                </div>
                <p className="muted" style={{ marginTop: 0 }}>
                  Proposed: {row.proposed_room || "a meeting room"}. Confirm on behalf of the requester, or open the case.
                </p>
                <div className="row" style={{ marginTop: "0.9rem" }}>
                  <button
                    className="btn accent"
                    disabled={busyId === o.outcome_id}
                    onClick={() => confirmRoom(o.outcome_id)}
                  >
                    Confirm booking
                  </button>
                  <Link className="btn secondary" href={`/outcomes/${o.outcome_id}`}>
                    Open request
                  </Link>
                </div>
              </div>
            );
          }

          if (!review?.review_id) return null;
          return (
            <div className="panel" key={review.review_id}>
              <div className="panel-head">
                <div>
                  <h3 style={{ marginBottom: "0.35rem" }}>{row.email?.subject || "Untitled email"}</h3>
                  <div className="chip-row">
                    <span className="badge">From {row.email?.sender || "unknown"}</span>
                    <StatusBadge status={review.status} />
                  </div>
                </div>
              </div>
              {review.reason && (
                <p className="muted" style={{ marginTop: 0 }}>
                  Why it paused: {review.reason}
                </p>
              )}
              <div className="cols-2" style={{ marginTop: "0.75rem" }}>
                <div>
                  <div className="muted" style={{ fontSize: "0.78rem", fontWeight: 600, marginBottom: "0.35rem" }}>
                    What they wrote
                  </div>
                  <div className="pre">{row.email?.body_text || "—"}</div>
                </div>
                <div>
                  <div className="muted" style={{ fontSize: "0.78rem", fontWeight: 600, marginBottom: "0.35rem" }}>
                    What the system understood
                  </div>
                  <div className="pre">{plainSummary(row.ai_decision?.output)}</div>
                </div>
              </div>
              <div className="row" style={{ marginTop: "0.9rem" }}>
                <button
                  className="btn accent"
                  disabled={busyId === review.review_id}
                  onClick={() => decide(review.review_id, "ACCEPT")}
                >
                  Approve & continue
                </button>
                <button
                  className="btn secondary"
                  disabled={busyId === review.review_id}
                  onClick={() => decide(review.review_id, "CLARIFY")}
                >
                  Ask for more info
                </button>
                <button
                  className="btn danger"
                  disabled={busyId === review.review_id}
                  onClick={() => decide(review.review_id, "REJECT")}
                >
                  Reject
                </button>
              </div>
            </div>
          );
        })}
        {rows.length === 0 && (
          <div className="panel empty">
            <strong>You’re all caught up</strong>
            Nothing is waiting for a decision right now.
          </div>
        )}
      </div>
    </AppShell>
  );
}
