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
    <AppShell>
      <h1 className="page-title">CloudMailin inbox</h1>
      <p className="page-sub">
        CloudMailin webhook → store → AI → outcome → SMTP reply in the same email thread. Prototype only —
        no Microsoft Graph.
      </p>
      {msg && <p className="badge danger">{msg}</p>}

      <div className="stack">
        <div className="panel">
          <h2>Status</h2>
          <p>
            Provider: <span className="badge accent">{cloudmailin?.provider || "CLOUDMAILIN"}</span>
          </p>
          <p>
            Inbound address:{" "}
            <span className="mono">{cloudmailin?.address || "set CLOUDMAILIN_ADDRESS in backend/.env"}</span>
          </p>
          <p>
            From (replies):{" "}
            <span className="mono">{cloudmailin?.from_email || "set CLOUDMAILIN_FROM_EMAIL"}</span>
          </p>
          <p>
            Webhook secret:{" "}
            <span className={`badge ${cloudmailin?.secret_configured ? "ok" : "warn"}`}>
              {cloudmailin?.secret_configured ? "configured" : "open (prototype)"}
            </span>
          </p>
          <p>
            SMTP outbound:{" "}
            <span className={`badge ${cloudmailin?.smtp_configured ? "ok" : "warn"}`}>
              {cloudmailin?.smtp_configured ? "ready — live replies enabled" : "not set — clarifications stored only"}
            </span>
          </p>
          <button className="btn secondary" onClick={load}>
            Refresh
          </button>
        </div>

        <div className="panel">
          <h2>CloudMailin setup</h2>
          <ol className="muted">
            <li>
              Create a free account at{" "}
              <a href="https://www.cloudmailin.com/" target="_blank" rel="noreferrer">
                cloudmailin.com
              </a>
            </li>
            <li>Copy the inbound address into <span className="mono">CLOUDMAILIN_ADDRESS</span></li>
            <li>
              Set format to <strong>JSON Normalized</strong>
            </li>
            <li>Set Target URL to the webhook below (use ngrok if the API is local)</li>
            <li>
              Optional for live replies: CloudMailin SMTP → <span className="mono">CLOUDMAILIN_SMTP_URL</span>
            </li>
          </ol>
          <p className="muted mono">Target URL</p>
          <p className="mono pre">{targetUrl}</p>
        </div>

        <div className="panel">
          <h2>Demo</h2>
          <ol className="muted">
            <li>
              Email the CloudMailin address:{" "}
              <em>&quot;I need a meeting room for 8 people tomorrow at 3 PM for 2 hours.&quot;</em>
            </li>
            <li>Incomplete: <em>&quot;I need a meeting room tomorrow.&quot;</em> → clarification reply</li>
            <li>Reply in-thread with details → same Outcome updates (no duplicate)</li>
            <li>Resend the same message → deduplicated</li>
          </ol>
        </div>
      </div>
    </AppShell>
  );
}
