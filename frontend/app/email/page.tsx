"use client";

import { AppShell } from "@/components/AppShell";
import { AsKpi, AsStatus } from "@/components/ui/PageBits";
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
      title="Mail Inbox"
      subtitle="Employee mail address — AdminServices reads every message and replies in-thread."
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Finance & mail" }, { label: "Mail Inbox" }]}
      actions={
        <button className="btn secondary" onClick={load}>
          Refresh
        </button>
      }
    >
      {msg ? <p className="badge danger">{msg}</p> : null}

      <div className="as-kpi-grid">
        <AsKpi label="Receiving" value={cloudmailin?.address ? "On" : "Off"} hint="Inbox ready for employees" />
        <AsKpi label="Sending replies" value={canReply ? "On" : "Off"} hint={canReply ? "Can write back" : "Receive only"} />
        <AsKpi label="Audience" value="Employees" hint="Only people in Master Data" />
        <AsKpi label="Status" value={canReply ? "Ready" : "Partial"} hint="Configure SMTP if needed" />
      </div>

      <div className="as-split">
        <section className="as-card">
          <div className="panel-head">
            <h2>Tell employees to write to</h2>
            <AsStatus status={canReply ? "Ready" : "Receive only"} />
          </div>
          <div className="mono pre" style={{ marginTop: "0.35rem", padding: "0.85rem", background: "#f8fafc", borderRadius: 8 }}>
            {cloudmailin?.address || "Not configured yet"}
          </div>
          <p className="muted" style={{ marginTop: "0.85rem", lineHeight: 1.5 }}>
            Load employees under Master Data first. Unknown senders get no reply and no ticket.
          </p>
          <Link href="/setup" className="btn accent" style={{ marginTop: "1rem", display: "inline-flex" }}>
            Open Master Data
          </Link>
        </section>
        <aside className="as-side-help">
          <h3>How it works</h3>
          <ul>
            <li>Employee mails the inbox address</li>
            <li>AdminServices opens or updates a request</li>
            <li>Teams get tasks; you approve when needed</li>
            <li>Replies stay in the same email thread</li>
          </ul>
        </aside>
      </div>
    </AppShell>
  );
}
