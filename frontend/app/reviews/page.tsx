"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export default function ReviewsPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  function load() {
    api("/reviews").then(setRows).catch((e) => setMsg(e.message));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AppShell>
      <h1 className="page-title">Human Review Queue</h1>
      <p className="page-sub">Accept, correct, clarify, or reject AI interpretations — every override is audited.</p>
      {msg && <p className="muted">{msg}</p>}
      <div className="stack">
        {rows.map((row) => (
          <div className="panel" key={row.review.review_id}>
            <div className="row">
              <span className="badge accent">confidence {row.ai_decision?.confidence ?? "—"}</span>
              <span className="muted">{row.review.reason}</span>
            </div>
            <h3>{row.email?.subject}</h3>
            <div className="pre">{row.email?.body_text}</div>
            <div className="pre">{JSON.stringify(row.ai_decision?.output, null, 2)}</div>
            <div className="row">
              {["ACCEPT", "CLARIFY", "REJECT"].map((action) => (
                <button
                  key={action}
                  className="btn secondary"
                  onClick={async () => {
                    await api(`/reviews/${row.review.review_id}/decide`, {
                      method: "POST",
                      body: JSON.stringify({ action, reason: `Prototype ${action}` }),
                    });
                    load();
                  }}
                >
                  {action}
                </button>
              ))}
            </div>
          </div>
        ))}
        {rows.length === 0 && <div className="panel muted">No pending reviews</div>}
      </div>
    </AppShell>
  );
}
