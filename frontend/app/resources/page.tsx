"use client";

import { AppShell } from "@/components/AppShell";
import { AsEmpty, AsStatus } from "@/components/ui/PageBits";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

const TYPES = [
  { id: "", label: "All" },
  { id: "MEETING_ROOM", label: "Meeting rooms" },
  { id: "PARKING_SLOT", label: "Parking" },
  { id: "DESK", label: "Desks" },
  { id: "SEAT", label: "Seats" },
  { id: "LAPTOP", label: "Laptops" },
  { id: "MONITOR", label: "Monitors" },
  { id: "ACCESS_CARD", label: "Access cards" },
];

export default function ResourcesPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [type, setType] = useState("");

  useEffect(() => {
    const q = type ? `?type=${type}` : "";
    api(`/resources${q}`).then(setRows).catch(console.error);
  }, [type]);

  return (
    <AppShell
      title="Assets & Rooms"
      subtitle="Meeting rooms, parking, desks, and other bookable assets across your offices."
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Operations" }, { label: "Assets & Rooms" }]}
    >
      <section className="as-card">
        <div className="panel-head">
          <h2>Asset directory</h2>
        </div>
        <div className="as-tabs" style={{ border: "none", padding: 0, marginBottom: "0.85rem", borderRadius: 0 }}>
          {TYPES.map((t) => (
            <button key={t.id || "ALL"} type="button" className={type === t.id ? "on" : ""} onClick={() => setType(t.id)}>
              {t.label}
            </button>
          ))}
        </div>
        {!rows.length ? (
          <AsEmpty title="No assets in this filter" body="Try another type, or import resources from Master Data." />
        ) : (
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
                  <AsStatus status={r.status} />
                </td>
                <td className="mono">{r.location_id || "—"}</td>
                <td className="mono">{r.allocated_to_person_id || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        )}
      </section>
    </AppShell>
  );
}
