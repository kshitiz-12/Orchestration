"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export default function FailuresPage() {
  const [rows, setRows] = useState<any[]>([]);

  function load() {
    api("/failures").then(setRows).catch(console.error);
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AppShell
      title="Failure console"
      subtitle="Failed stage, error, retry count — original event retained and reprocessable."
      actions={
        <button className="btn secondary" onClick={load}>
          Refresh
        </button>
      }
    >
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Job</th>
              <th>Stage</th>
              <th>Status</th>
              <th>Attempts</th>
              <th>Error</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((j) => (
              <tr key={j.job_id}>
                <td className="mono">{j.job_id}</td>
                <td>{j.stage}</td>
                <td>
                  <span className="badge danger">{j.status}</span>
                </td>
                <td>{j.attempts}</td>
                <td className="muted">{j.last_error}</td>
                <td>
                  <button
                    className="btn"
                    onClick={async () => {
                      await api(`/failures/${j.job_id}/reprocess`, { method: "POST" });
                      load();
                    }}
                  >
                    Reprocess
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="muted">No failed jobs</p>}
      </div>
    </AppShell>
  );
}
