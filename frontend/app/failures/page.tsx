"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export default function FailuresPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  function load() {
    api("/failures")
      .then((r) => setRows(Array.isArray(r) ? r : []))
      .catch((e) => setMsg(e.message));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AppShell
      title="Problems"
      subtitle="Things that failed while processing email. You can retry them."
      actions={
        <button className="btn secondary" onClick={load}>
          Refresh
        </button>
      }
    >
      {msg && <p className="badge danger">{msg}</p>}
      <div className="panel">
        {rows.length === 0 ? (
          <div className="empty">
            <strong>No problems</strong>
            Everything is processing cleanly.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>What failed</th>
                <th>Status</th>
                <th>Tries</th>
                <th>Error</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((j) => (
                <tr key={j.job_id}>
                  <td>
                    <div className="mono">{j.job_id}</div>
                    <div className="muted" style={{ fontSize: "0.78rem" }}>
                      {j.stage || j.job_type}
                    </div>
                  </td>
                  <td>{j.status}</td>
                  <td>{j.attempts}</td>
                  <td className="muted">{j.last_error || "—"}</td>
                  <td>
                    <button
                      className="btn secondary"
                      onClick={async () => {
                        try {
                          await api(`/failures/${j.job_id}/reprocess`, { method: "POST" });
                          setMsg("Retry queued.");
                          load();
                        } catch (e: any) {
                          setMsg(e.message);
                        }
                      }}
                    >
                      Retry
                    </button>
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
