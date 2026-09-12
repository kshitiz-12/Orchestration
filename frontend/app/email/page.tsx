"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export default function EmailInboxPage() {
  const [cloudmailin, setCloudmailin] = useState<any>(null);
  const [msg, setMsg] = useState("");

  function load() {
    api("/webhooks/cloudmailin")
      .then(setCloudmailin)
      .catch((e) => setMsg(e.message));
  }

  useEffect(() => {
    load();
  }, []);

  const canReply = cloudmailin?.can_send_replies || cloudmailin?.smtp_configured;

  return (
    <AppShell
      title="Email intake"
      subtitle="People email this address. The system reads the mail and creates a request."
      actions={
        <button className="btn secondary" onClick={load}>
          Refresh
        </button>
      }
    >
      {msg && <p className="badge danger">{msg}</p>}

      <div className="grid kpis" style={{ marginBottom: "1.25rem" }}>
        <div className="kpi">
          <div className="label">Receiving mail</div>
          <div className="value" style={{ fontSize: "1.2rem" }}>
            {cloudmailin?.address ? "Yes" : "Not set"}
          </div>
          <div className="hint">Inbox address configured</div>
        </div>
        <div className="kpi">
          <div className="label">Sending replies</div>
          <div className="value" style={{ fontSize: "1.2rem" }}>
            {canReply ? "Yes" : "No"}
          </div>
          <div className="hint">{canReply ? "Clarification emails can go out" : "Replies are saved only"}</div>
        </div>
        <div className="kpi">
          <div className="label">Security check</div>
          <div className="value" style={{ fontSize: "1.2rem" }}>
            {cloudmailin?.secret_configured ? "On" : "Open"}
          </div>
          <div className="hint">Webhook protection</div>
        </div>
      </div>

      <div className="cols-2">
        <div className="panel">
          <div className="panel-head">
            <h2>Addresses</h2>
            <span className={`badge ${canReply ? "ok" : "warn"}`}>
              {canReply ? "Ready" : "Receive only"}
            </span>
          </div>
          <div className="stack">
            <div>
              <div className="muted" style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                People should email
              </div>
              <div className="mono pre" style={{ marginTop: "0.35rem" }}>
                {cloudmailin?.address || "Not configured"}
              </div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                Replies come from
              </div>
              <div className="mono" style={{ marginTop: "0.35rem" }}>
                {cloudmailin?.from_email || "Not configured"}
              </div>
            </div>
          </div>
        </div>

        <div className="panel">
          <h2 style={{ marginBottom: "0.75rem" }}>How to try it</h2>
          <ol className="muted" style={{ margin: 0, paddingLeft: "1.1rem", lineHeight: 1.55 }}>
            <li>
              Send: <em>&quot;I need a meeting room for 3 people.&quot;</em> to the address above.
            </li>
            <li>Open <strong>Home</strong> or <strong>All requests</strong> — a new case appears.</li>
            <li>If details are missing, the system emails clarifying questions.</li>
            <li>Reply to that email (use Reply) so it stays on the same case.</li>
          </ol>
        </div>
      </div>
    </AppShell>
  );
}
