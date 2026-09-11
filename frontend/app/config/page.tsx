"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export default function ConfigPage() {
  const [templates, setTemplates] = useState<any[]>([]);
  const [rules, setRules] = useState<any[]>([]);
  const [notes, setNotes] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([api("/config/templates"), api("/config/rules"), api("/config/notifications")]).then(
      ([t, r, n]) => {
        setTemplates(t);
        setRules(r);
        setNotes(n);
      }
    );
  }, []);

  return (
    <AppShell title="Configuration" subtitle="Outcome templates, rules, SLAs, notifications, evidence requirements.">
      <div className="stack">
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
