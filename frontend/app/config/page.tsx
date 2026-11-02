"use client";

import { AppShell } from "@/components/AppShell";
import { AsTabs } from "@/components/ui/PageBits";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

const TABS = [
  { id: "controls", label: "Demo controls" },
  { id: "templates", label: "Templates" },
  { id: "rules", label: "Rules" },
  { id: "notifications", label: "Notifications" },
] as const;

export default function ConfigPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("controls");
  const [templates, setTemplates] = useState<any[]>([]);
  const [rules, setRules] = useState<any[]>([]);
  const [notes, setNotes] = useState<any[]>([]);
  const [policy, setPolicy] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");

  function load() {
    Promise.all([
      api("/config/templates"),
      api("/config/rules"),
      api("/config/notifications"),
      api("/policy/meeting-room").catch(() => null),
    ]).then(([t, r, n, p]) => {
      setTemplates(t);
      setRules(r);
      setNotes(n);
      setPolicy(p);
    });
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AppShell
      title="Settings"
      subtitle="Turnaround times, notifications, and request rules for your company."
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Settings" }]}
    >
      <AsTabs tabs={[...TABS]} value={tab} onChange={(id) => setTab(id as typeof tab)} />

      {tab === "controls" ? (
        <section className="as-card">
          <div className="panel-head">
            <h2>Demo controls</h2>
          </div>
          <p className="muted" style={{ marginTop: 0 }}>
            Soft reset clears emails, outcomes, and reviews. Org masters (people, rooms, rules) stay.
          </p>
          <div className="row" style={{ gap: "0.75rem", flexWrap: "wrap" }}>
            <button
              className="btn secondary"
              disabled={busy === "reset"}
              onClick={async () => {
                if (!window.confirm("Clear all demo cases and emails?")) return;
                setBusy("reset");
                try {
                  const res = await api("/demo/reset", { method: "POST" });
                  setMsg(`Demo reset: ${res.message || "ok"}`);
                  load();
                } catch (e: any) {
                  setMsg(e.message || "Reset failed");
                } finally {
                  setBusy("");
                }
              }}
            >
              Soft reset demo data
            </button>
            <button
              className="btn secondary"
              disabled={busy === "eval"}
              onClick={async () => {
                setBusy("eval");
                try {
                  const res = await api("/evals/meeting-room", { method: "POST" });
                  setMsg(`Eval ${res.passed}/${res.total} passed (${Math.round((res.pass_rate || 0) * 100)}%)`);
                } catch (e: any) {
                  setMsg(e.message || "Eval failed");
                } finally {
                  setBusy("");
                }
              }}
            >
              Run golden eval
            </button>
            <button
              className="btn secondary"
              disabled={busy === "sla"}
              onClick={async () => {
                setBusy("sla");
                try {
                  const res = await api("/sla/tick", { method: "POST" });
                  setMsg(
                    `SLA: ${res.overdue_tasks || 0} overdue, ${res.escalated_tasks || 0} escalated, ${res.outcomes_marked_at_risk || 0} at risk`
                  );
                } catch (e: any) {
                  setMsg(e.message || "SLA tick failed");
                } finally {
                  setBusy("");
                }
              }}
            >
              Tick SLA clocks
            </button>
          </div>
          {msg ? <p className="badge ok" style={{ marginTop: "0.75rem" }}>{msg}</p> : null}
          {policy ? (
            <div style={{ marginTop: "1.25rem" }}>
              <h3 style={{ margin: "0 0 0.35rem", fontSize: "0.95rem" }}>
                Meeting-room policy v{policy.version}
              </h3>
              <p className="muted" style={{ marginTop: 0 }}>
                {policy.code} · auto-book ≥ {policy.auto_book_min_score} · buffers{" "}
                {policy.setup_buffer_internal_minutes}/{policy.release_buffer_internal_minutes} (internal)
              </p>
            </div>
          ) : null}
        </section>
      ) : null}

      {tab === "templates" ? (
        <section className="as-card">
          <div className="panel-head">
            <h2>Outcome templates</h2>
          </div>
          <div className="as-settings-list">
            {templates.map((t) => (
              <div key={t.template_id} className="as-settings-row">
                <div>
                  <strong>{t.code}</strong>
                  <span className="muted"> — {t.name}</span>
                </div>
                <span className="muted" style={{ fontSize: "0.8rem" }}>
                  {t.tasks?.length || 0} tasks · {t.requirements?.length || 0} requirements · prefix {t.case_prefix}
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {tab === "rules" ? (
        <section className="as-card">
          <div className="panel-head">
            <h2>Rules</h2>
          </div>
          <div className="as-settings-list">
            {rules.map((r) => (
              <div key={r.rule_id} className="as-settings-row">
                <strong>{r.code}</strong>
                <pre className="as-pre">{JSON.stringify(r.config, null, 2)}</pre>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {tab === "notifications" ? (
        <section className="as-card">
          <div className="panel-head">
            <h2>Notification templates</h2>
          </div>
          <div className="as-settings-list">
            {notes.map((n) => (
              <div key={n.template_id} className="as-settings-row">
                <strong>{n.code}</strong>
                <span className="muted">{n.subject_template}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </AppShell>
  );
}
