"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export default function ResourcesPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [type, setType] = useState("");

  useEffect(() => {
    const q = type ? `?type=${type}` : "";
    api(`/resources${q}`).then(setRows).catch(console.error);
  }, [type]);

  return (
    <AppShell title="Resources" subtitle="Seats, parking, chairs, devices — allocation, reservation, conflict.">
      <div className="row" style={{ marginBottom: "1rem" }}>
        {["", "SEAT", "CHAIR", "PARKING_SLOT", "LAPTOP", "MONITOR", "ACCESS_CARD"].map((t) => (
          <button key={t || "ALL"} className="btn secondary" onClick={() => setType(t)}>
            {t || "ALL"}
          </button>
        ))}
      </div>
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Location</th>
              <th>Allocated to</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.resource_id}>
                <td>{r.name}</td>
                <td>{r.type}</td>
                <td>
                  <span className={`badge ${r.status === "CONFLICT" ? "danger" : ""}`}>{r.status}</span>
                </td>
                <td className="mono">{r.location_id || "—"}</td>
                <td className="mono">{r.allocated_to_person_id || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
