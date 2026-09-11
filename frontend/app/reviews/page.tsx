"use client";

import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

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
        body: JSON.stringify({ action, reason: `Prototype ${action}` }),
      });
      load();
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <AppShell
      title="Human review"
      subtitle="Accept, clarify, or reject AI interpretations. Every override is audited."
      actions={
        <button className="btn secondary" onClick={load}>
          Refresh
        </button>
      }
    >
      {msg && <p className="badge danger">{msg}</p>}
      <div className="stack">
        {rows.map((row) => (
          <div className="panel" key={row.review.review_id}>
            <div className="panel-head">
              <div>
                <h3 style={{ marginBottom: "0.35rem" }}>{row.email?.subject || "Untitled email"}</h3>
                <div className="chip-row">
                  <span className="badge accent">
                    confidence {row.ai_decision?.confidence ?? "—"}
                  </span>
                  <StatusBadge status={row.review.status} />
                  <span className="badge">{row.ai_decision?.route || "route?"}</span>
                </div>
              </div>
            </div>
            {row.review.reason && <p className="muted">{row.review.reason}</p>}
            <div className="cols-2" style={{ marginTop: "0.75rem" }}>
              <div>
                <div className="muted" style={{ fontSize: "0.78rem", fontWeight: 600, marginBottom: "0.35rem" }}>
                  Email
                </div>
                <div className="pre">{row.email?.body_text || "—"}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: "0.78rem", fontWeight: 600, marginBottom: "0.35rem" }}>
                  AI output
                </div>
                <div className="pre">{JSON.stringify(row.ai_decision?.output, null, 2)}</div>
              </div>
            </div>
            <div className="row" style={{ marginTop: "0.9rem" }}>
              <button
                className="btn accent"
                disabled={busyId === row.review.review_id}
                onClick={() => decide(row.review.review_id, "ACCEPT")}
              >
                Accept
              </button>
              <button
                className="btn secondary"
                disabled={busyId === row.review.review_id}
                onClick={() => decide(row.review.review_id, "CLARIFY")}
              >
                Clarify
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
            <strong>Queue clear</strong>
            No pending human reviews.
          </div>
        )}
      </div>
    </AppShell>
  );
}
