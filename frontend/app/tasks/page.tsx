"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

const ACTIONS = ["ACCEPTED", "IN_PROGRESS", "ON_HOLD", "COMPLETED_PENDING_EVIDENCE", "CLOSED"];

export default function TasksPage() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  function load() {
    api("/tasks").then(setTasks).catch((e) => setMsg(e.message));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AppShell>
      <h1 className="page-title">Task Workspace</h1>
      <p className="page-sub">Accept, start, hold, complete — evidence required where configured.</p>
      {msg && <p className="badge danger">{msg}</p>}
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Task</th>
              <th>Outcome</th>
              <th>Owner</th>
              <th>Status</th>
              <th>Evidence</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.task_id}>
                <td>
                  {t.title}
                  {t.is_blocked && <span className="badge warn"> blocked</span>}
                </td>
                <td className="mono">{t.outcome_id}</td>
                <td>{t.owner_role}</td>
                <td>{t.status}</td>
                <td>{t.evidence_required ? "required" : "—"}</td>
                <td>
                  <div className="row">
                    {ACTIONS.map((status) => (
                      <button
                        key={status}
                        className="btn secondary"
                        onClick={async () => {
                          try {
                            await api(`/tasks/${t.task_id}/status`, {
                              method: "POST",
                              body: JSON.stringify({ status, resolution: `Set to ${status}` }),
                            });
                            setMsg("");
                            load();
                          } catch (e: any) {
                            setMsg(e.message);
                          }
                        }}
                      >
                        {status.replaceAll("_", " ").toLowerCase()}
                      </button>
                    ))}
                    {t.evidence_required && (
                      <button
                        className="btn"
                        onClick={async () => {
                          await api(`/evidence?outcome_id=${t.outcome_id}`, {
                            method: "POST",
                            body: JSON.stringify({
                              evidence_type: "PHOTO_OR_RECORD",
                              description: "Prototype evidence",
                              task_id: t.task_id,
                              record_ref: `demo-${t.task_id}`,
                            }),
                          });
                          const list = await api(`/outcomes/${t.outcome_id}`);
                          const ev = (list.evidence || []).find((e: any) => e.task_id === t.task_id);
                          if (ev) await api(`/evidence/${ev.evidence_id}/verify`, { method: "POST" });
                          load();
                        }}
                      >
                        Upload+verify evidence
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
