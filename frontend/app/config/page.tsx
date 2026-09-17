"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export default function ConfigPage() {
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
    <AppShell title="Configuration" subtitle="Outcome templates, rules, SLAs, notifications, evidence requirements.">
      <div className="stack">
        <div className="panel">
          <h2>Demo controls</h2>
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
          {msg && <p className="badge ok" style={{ marginTop: "0.75rem" }}>{msg}</p>}
        </div>

        {policy && (
          <div className="panel">
            <h2>Meeting-room policy v{policy.version}</h2>
            <div className="muted" style={{ marginBottom: "0.5rem" }}>
              {policy.code} · auto-book ≥ {policy.auto_book_min_score} · buffers{" "}
              {policy.setup_buffer_internal_minutes}/{policy.release_buffer_internal_minutes} (internal)
            </div>
            <div className="pre">{JSON.stringify(policy, null, 2)}</div>
          </div>
        )}

        <div className="panel">
          <h2>Outcome templates</h2>
          {templates.map((t) => (
            <div key={t.template_id} style={{ marginBottom: "0.75rem" }}>
              <strong>{t.code}</strong> — {t.name}
              <div className="muted">
                {t.tasks?.length || 0} tasks · {t.requirements?.length || 0} requirements · prefix {t.case_prefix}
              </div>
            </div>
          ))}
        </div>
        <div className="panel">
          <h2>Rules</h2>
          {rules.map((r) => (
            <div key={r.rule_id}>
              <strong>{r.code}</strong>
              <div className="pre">{JSON.stringify(r.config, null, 2)}</div>
            </div>
          ))}
        </div>
        <div className="panel">
          <h2>Notification templates</h2>
          {notes.map((n) => (
            <div key={n.template_id} className="muted">
              {n.code}: {n.subject_template}
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
