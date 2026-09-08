"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function OutcomesPage() {
  const [rows, setRows] = useState<any[]>([]);

  useEffect(() => {
    api("/outcomes").then(setRows).catch(console.error);
  }, []);

  return (
    <AppShell>
      <h1 className="page-title">Outcomes</h1>
      <p className="page-sub">Parent business results — not tickets.</p>
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Outcome ID</th>
              <th>Type</th>
              <th>Requester</th>
              <th>Date</th>
              <th>Readiness</th>
              <th>Blocker</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((o) => (
              <tr key={o.outcome_id}>
                <td>
                  <Link href={`/outcomes/${o.outcome_id}`}>{o.case_reference}</Link>
                </td>
                <td>{o.template_code}</td>
                <td>{o.requester_email}</td>
                <td>{new Date(o.created_at).toLocaleString()}</td>
                <td>{o.readiness_pct}%</td>
                <td>{(o.blockers || []).map((b: any) => b.code).join(", ") || "—"}</td>
                <td>
                  <span className="badge">{o.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
