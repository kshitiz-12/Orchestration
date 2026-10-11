"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import Link from "next/link";
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
      title="Mail inbox"
      subtitle="The address employees use. Desk reads every message and replies in the same thread."
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
          <div className="value" style={{ fontSize: "1.15rem" }}>
            {cloudmailin?.address ? "Yes" : "Not set"}
          </div>
          <div className="hint">Inbox ready for employees</div>
        </div>
        <div className="kpi">
          <div className="label">Sending replies</div>
          <div className="value" style={{ fontSize: "1.15rem" }}>
            {canReply ? "Yes" : "No"}
          </div>
          <div className="hint">{canReply ? "Desk can write back" : "Ask your provider to enable sending"}</div>
        </div>
        <div className="kpi">
          <div className="label">Who gets a reply</div>
          <div className="value" style={{ fontSize: "1.15rem" }}>
            Employees
          </div>
          <div className="hint">Only people in Company data</div>
        </div>
      </div>

      <div className="cols-2">
        <div className="panel">
          <div className="panel-head">
            <h2>Tell employees to write to</h2>
            <span className={`badge ${canReply ? "ok" : "warn"}`}>{canReply ? "Ready" : "Receive only"}</span>
          </div>
          <div className="mono pre" style={{ marginTop: "0.35rem" }}>
            {cloudmailin?.address || "Not configured yet — contact your Desk provider"}
          </div>
          <p className="muted" style={{ marginTop: "0.85rem", lineHeight: 1.5 }}>
            Load employees under Company data first. Unknown senders get no reply and no ticket.
          </p>
          <Link href="/setup" className="btn accent" style={{ marginTop: "1rem", display: "inline-flex" }}>
            Manage company data
          </Link>
        </div>
        <div className="panel">
          <div className="panel-head">
            <h2>How it works</h2>
          </div>
          <div className="stack" style={{ gap: "0.65rem" }}>
            <p className="muted" style={{ margin: 0, lineHeight: 1.5 }}>
              1. Employee emails this address with a request.
            </p>
            <p className="muted" style={{ margin: 0, lineHeight: 1.5 }}>
              2. Desk asks for anything missing, then notifies the right team at their branch.
            </p>
            <p className="muted" style={{ margin: 0, lineHeight: 1.5 }}>
              3. The team replies on the work order; the employee gets updates in the same thread.
            </p>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
