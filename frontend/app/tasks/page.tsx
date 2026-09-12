"use client";

import { AppShell } from "@/components/AppShell";
import { StatusBadge } from "@/components/Status";
import { api } from "@/lib/api";
import { friendlyStatus } from "@/lib/labels";
import Link from "next/link";
import { useEffect, useState } from "react";

const ACTIONS = [
  { status: "ACCEPTED", label: "Accept" },
  { status: "IN_PROGRESS", label: "Start" },
  { status: "ON_HOLD", label: "Hold" },
  { status: "COMPLETED_PENDING_EVIDENCE", label: "Done" },
  { status: "CLOSED", label: "Close" },
];

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
    <AppShell
      title="Team tasks"
      subtitle="Work items for operators. Update status as you go."
      actions={
        <button className="btn secondary" onClick={load}>
          Refresh
        </button>
      }
    >
      {msg && <p className="badge danger">{msg}</p>}
      <div className="panel">
        {tasks.length === 0 ? (
          <div className="empty">
            <strong>No tasks yet</strong>
            Tasks appear when a request is created from email.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Task</th>
                <th>Request</th>
                <th>Owner</th>
                <th>Status</th>
                <th>Update</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.task_id}>
                  <td>
                    {t.title}
                    {t.is_blocked && <span className="badge warn"> blocked</span>}
                    {t.evidence_required && (
                      <div className="muted" style={{ fontSize: "0.75rem" }}>
                        Proof required
                      </div>
                    )}
                  </td>
                  <td>
                    <Link className="table-link" href={`/outcomes/${t.outcome_id}`}>
                      Open
                    </Link>
                  </td>
                  <td>{t.owner_role}</td>
                  <td>
                    <StatusBadge status={friendlyStatus(t.status)} />
                  </td>
                  <td>
                    <div className="row">
                      {ACTIONS.map((a) => (
                        <button
                          key={a.status}
                          className="btn secondary"
                          onClick={async () => {
                            try {
                              await api(`/tasks/${t.task_id}/status`, {
                                method: "POST",
                                body: JSON.stringify({ status: a.status, resolution: `Set to ${a.status}` }),
                              });
                              setMsg("");
                              load();
                            } catch (e: any) {
                              setMsg(e.message);
                            }
                          }}
                        >
                          {a.label}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </AppShell>
  );
}
