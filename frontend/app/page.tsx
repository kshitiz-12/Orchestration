"use client";

import { AppShell } from "@/components/AppShell";
import { uploadFigures } from "@/components/UploadMeter";
import { api } from "@/lib/api";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

export default function DashboardPage() {
  const [kpis, setKpis] = useState<any>(null);
  const [setup, setSetup] = useState<any>(null);
  const [vendors, setVendors] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [k, s, v] = await Promise.all([
        api("/dashboard/kpis"),
        api("/setup/status").catch(() => null),
        api<any[]>("/vendors").catch(() => []),
      ]);
      setKpis(k && typeof k === "object" ? k : null);
      setSetup(s);
      setVendors(Array.isArray(v) ? v : []);
    } catch (e: any) {
      setError(e.message || "Could not load dashboard");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const waitingYou =
    kpis?.waiting_on_you != null
      ? Number(kpis.waiting_on_you)
      : Number(kpis?.human_reviews || 0) +
        Number(kpis?.pending_approvals || 0) +
        Number(kpis?.pending_confirmations || 0);
  const openCases = Number(kpis?.outcomes_active || 0);
  const pastSla = Number(kpis?.past_sla || 0);
  const closed = Number(kpis?.outcomes_closed || kpis?.closed || 0);
  const employees = Number(setup?.employees || 0);
  const locations = Number(setup?.locations || 0);
  const upload = uploadFigures(setup?.excel_upload);
  const invited = vendors.filter((x) => String(x.status || "").toUpperCase() === "INVITED").length;
  const activeVendors = vendors.filter((x) => String(x.status || "").toUpperCase() === "ACTIVE").length;
  const onboarding = vendors.filter((x) =>
    ["INVITED", "REGISTERED", "UNDER_REVIEW", "PENDING"].includes(String(x.status || "").toUpperCase())
  ).length;

  const setupScore = useMemo(() => {
    const parts = [
      employees > 0 ? 1 : 0,
      locations > 0 ? 1 : 0,
      Number(setup?.departments || 0) > 0 ? 1 : 0,
      vendors.length > 0 ? 1 : 0,
    ];
    return Math.round((parts.reduce((a, b) => a + b, 0) / parts.length) * 100);
  }, [employees, locations, setup, vendors.length]);

  const chart = [
    { label: "Open", value: openCases, color: "#2563eb" },
    { label: "Needs you", value: waitingYou, color: "#f59e0b" },
    { label: "Past due", value: pastSla, color: "#ef4444" },
    { label: "Closed", value: closed, color: "#22c55e" },
  ];
  const chartMax = Math.max(1, ...chart.map((c) => c.value));

  return (
    <AppShell
      title="Dashboard"
      subtitle="Live view of facilities requests, vendor onboarding, and master-data readiness."
      breadcrumbs={[{ label: "AdminServices" }, { label: "Dashboard" }]}
      actions={
        <button className="btn secondary" onClick={load} disabled={busy}>
          {busy ? "Refreshing…" : "Refresh"}
        </button>
      }
    >
      {error ? (
        <div className="as-card" style={{ marginBottom: "1rem", borderColor: "#f0b4ae" }}>
          <strong style={{ color: "var(--danger)" }}>{error}</strong>
        </div>
      ) : null}

      <div className="as-kpi-grid">
        <Link href="/outcomes" className="as-kpi">
          <span className="label">Open requests</span>
          <span className="value">{openCases}</span>
          <span className="hint">Still with the teams</span>
        </Link>
        <Link href="/reviews" className="as-kpi">
          <span className="label">Needs your decision</span>
          <span className="value">{waitingYou}</span>
          <span className="hint">Approvals & confirmations</span>
        </Link>
        <Link href="/outcomes" className={`as-kpi ${pastSla > 0 ? "hot" : ""}`}>
          <span className="label">Past due</span>
          <span className="value">{pastSla}</span>
          <span className="hint">Missed agreed time</span>
        </Link>
        <Link href="/vendors/onboarding" className="as-kpi">
          <span className="label">Vendor pipeline</span>
          <span className="value">{onboarding}</span>
          <span className="hint">
            {invited} invited · {activeVendors} active
          </span>
        </Link>
      </div>

      <div className="as-dash-grid">
        <section className="as-card">
          <div className="panel-head">
            <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Request mix</h2>
            <Link href="/outcomes" className="btn ghost">
              Open facilities
            </Link>
          </div>
          <div className="as-chart-bars">
            {chart.map((row) => (
              <div key={row.label} className="as-chart-row">
                <span>{row.label}</span>
                <div className="as-chart-track">
                  <span
                    className="as-chart-fill"
                    style={{
                      width: `${Math.round((row.value / chartMax) * 100)}%`,
                      background: row.color,
                    }}
                  />
                </div>
                <strong>{row.value}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="as-card">
          <div className="panel-head">
            <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Setup readiness</h2>
            <Link href="/setup" className="btn ghost">
              Master data
            </Link>
          </div>
          <div className="as-circle-wrap">
            <div
              className="as-circle"
              style={{ background: `conic-gradient(#2563eb ${setupScore}%, #e5e7eb 0)` }}
            >
              <div className="as-circle-inner">
                <strong>{setupScore}%</strong>
                <span>Complete</span>
              </div>
            </div>
          </div>
          <ul className="vo-checks" style={{ marginTop: "0.75rem" }}>
            <li className={employees > 0 ? "ok" : ""}>
              {employees > 0 ? "✓" : "○"} Employees on file ({employees})
            </li>
            <li className={locations > 0 ? "ok" : ""}>
              {locations > 0 ? "✓" : "○"} Offices ({locations})
            </li>
            <li className={vendors.length > 0 ? "ok" : ""}>
              {vendors.length > 0 ? "✓" : "○"} Vendors ({vendors.length})
            </li>
            <li className={upload.percent >= 100 ? "ok" : ""}>
              {upload.percent >= 100 ? "✓" : "○"} Last Excel {upload.percent}%
            </li>
          </ul>
        </section>
      </div>

      <section className="as-card">
        <div className="panel-head">
          <h2 style={{ margin: 0, fontSize: "1.05rem" }}>Quick actions</h2>
        </div>
        <div className="as-actions-grid">
          <Link href="/setup" className="as-action">
            <strong>Import employees</strong>
            <span>Upload Part 1 workbook or employees sheet into Master Data.</span>
          </Link>
          <Link href="/vendors/onboarding" className="as-action">
            <strong>Invite vendor</strong>
            <span>Start the six-step onboarding and mail the registration link.</span>
          </Link>
          <Link href="/vendors" className="as-action">
            <strong>Vendor directory</strong>
            <span>Score, activate, or open an in-progress onboarding draft.</span>
          </Link>
          <Link href="/chat" className="as-action">
            <strong>Desk chat</strong>
            <span>Ask about records or drop Excel for a guided import.</span>
          </Link>
        </div>
      </section>
    </AppShell>
  );
}
