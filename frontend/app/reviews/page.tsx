"use client";

import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
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
      .then(setRows)
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

  return (
    <AppShell
      title="Needs your decision"
      subtitle="These requests paused until someone confirms what to do next."
      actions={
        <button className="btn secondary" onClick={load}>
          Refresh
        </button>
      }
    >
      {msg && <p className="badge ok">{msg}</p>}
      <div className="stack">
        {rows.map((row) => (
          <div className="panel" key={row.review.review_id}>
            <div className="panel-head">
              <div>
                <h3 style={{ marginBottom: "0.35rem" }}>{row.email?.subject || "Untitled email"}</h3>
                <div className="chip-row">
                  <span className="badge">From {row.email?.sender || "unknown"}</span>
                  <StatusBadge status={row.review.status} />
                </div>
              </div>
            </div>
            {row.review.reason && (
              <p className="muted" style={{ marginTop: 0 }}>
                Why it paused: {row.review.reason}
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
                disabled={busyId === row.review.review_id}
                onClick={() => decide(row.review.review_id, "ACCEPT")}
              >
                Approve & continue
              </button>
              <button
                className="btn secondary"
                disabled={busyId === row.review.review_id}
                onClick={() => decide(row.review.review_id, "CLARIFY")}
              >
                Ask for more info
              </button>
              <button
                className="btn danger"
                disabled={busyId === row.review.review_id}
                onClick={() => decide(row.review.review_id, "REJECT")}
              >
                Reject
              </button>
            </div>
          </div>
        ))}
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
