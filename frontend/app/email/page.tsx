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

  const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";
  const secretHint = cloudmailin?.secret_configured ? "YOUR_SECRET" : "";
  const targetUrl = `${base}${cloudmailin?.webhook_path || "/webhooks/cloudmailin"}${
    secretHint ? `?secret=${secretHint}` : ""
  }`;

  return (
    <AppShell
      title="CloudMailin"
      subtitle="Inbound: CloudMailin. Outbound: Gmail SMTP App Password (real inbox delivery)."
      actions={
        <button className="btn secondary" onClick={load}>
          Refresh status
        </button>
      }
    >
      {msg && <p className="badge danger">{msg}</p>}

      <div className="grid kpis" style={{ marginBottom: "1.25rem" }}>
        <div className="kpi">
          <div className="label">Provider</div>
          <div className="value" style={{ fontSize: "1.2rem" }}>
            {cloudmailin?.provider || "CLOUDMAILIN"}
          </div>
        </div>
        <div className="kpi">
          <div className="label">Webhook secret</div>
          <div className="value" style={{ fontSize: "1.2rem" }}>
            {cloudmailin?.secret_configured ? "On" : "Open"}
          </div>
          <div className="hint">{cloudmailin?.secret_configured ? "Configured" : "Prototype mode"}</div>
        </div>
        <div className="kpi">
          <div className="label">SMTP outbound</div>
          <div className="value" style={{ fontSize: "1.2rem" }}>
            {cloudmailin?.can_send_replies ? "Ready" : "Off"}
          </div>
          <div className="hint">
            {cloudmailin?.outbound_channel === "gmail_smtp"
              ? "Gmail SMTP"
              : cloudmailin?.can_send_replies
                ? "Configured"
                : "Add App Password"}
          </div>
        </div>
      </div>

      <div className="cols-2">
        <div className="panel">
          <div className="panel-head">
            <h2>Connection</h2>
            <span className={`badge ${cloudmailin?.can_send_replies ? "ok" : "warn"}`}>
              {cloudmailin?.can_send_replies ? "Full loop" : "Inbound only"}
            </span>
          </div>
          <div className="stack">
            <div>
              <div className="muted" style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                Inbound address
              </div>
              <div className="mono pre" style={{ marginTop: "0.35rem" }}>
                {cloudmailin?.address || "Set CLOUDMAILIN_ADDRESS"}
              </div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                From (replies)
              </div>
              <div className="mono" style={{ marginTop: "0.35rem" }}>
                {cloudmailin?.from_email || "Set OUTBOUND_SMTP_FROM"}
              </div>
            </div>
            <div>
              <div className="muted" style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                Target URL (JSON Normalized)
              </div>
              <div className="mono pre" style={{ marginTop: "0.35rem" }}>
                {targetUrl}
              </div>
            </div>
          </div>
        </div>

        <div className="panel">
          <h2 style={{ marginBottom: "0.75rem" }}>Demo script</h2>
          <ol className="muted" style={{ margin: 0, paddingLeft: "1.1rem", lineHeight: 1.55 }}>
            <li>
              Google Account → Security → 2-Step Verification → App passwords → set{" "}
              <span className="mono">OUTBOUND_SMTP_*</span> on Render
            </li>
            <li>
              Email CloudMailin: <em>&quot;I need a meeting room tomorrow.&quot;</em> → clarification
              lands in your Gmail (From = your App Password account)
            </li>
            <li>Reply in-thread with details → same Outcome updates</li>
            <li>Or use Outcomes → Resend clarification after SMTP is set</li>
          </ol>
        </div>
      </div>
    </AppShell>
  );
}
