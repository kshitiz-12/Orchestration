"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function HomePage() {
  const [kpis, setKpis] = useState<any>(null);
  const [outcomes, setOutcomes] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api("/dashboard/kpis"), api("/outcomes?limit=8")])
      .then(([k, o]) => {
        setKpis(k);
        setOutcomes(o);
      })
      .catch((e) => setError(e.message));
  }, []);

  return (
    <AppShell>
      <h1 className="page-title">Operations Dashboard</h1>
      <p className="page-sub">Governed outcomes from unstructured email — readiness, blockers, approvals, failures.</p>
      {error && <p className="badge danger">{error}</p>}
      <div className="grid kpis">
        {[
          ["Active outcomes", kpis?.outcomes_active],
          ["At risk", kpis?.at_risk],
          ["Overdue tasks", kpis?.overdue_tasks],
          ["Approvals", kpis?.pending_approvals],
          ["Human reviews", kpis?.human_reviews],
          ["Failures", kpis?.failures],
        ].map(([label, value]) => (
          <div className="kpi" key={label as string}>
            <div className="label">{label}</div>
            <div className="value">{value ?? "—"}</div>
          </div>
        ))}
      </div>
      <div className="panel">
        <h2>New / recent cases</h2>
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>Type</th>
              <th>Requester</th>
              <th>Status</th>
              <th>Readiness</th>
            </tr>
          </thead>
          <tbody>
            {outcomes.map((o) => (
              <tr key={o.outcome_id}>
                <td>
                  <Link href={`/outcomes/${o.outcome_id}`}>{o.case_reference}</Link>
                </td>
                <td>{o.template_code}</td>
                <td>{o.requester_email}</td>
                <td>
                  <span className="badge">{o.status}</span>
                </td>
                <td>{o.readiness_pct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
