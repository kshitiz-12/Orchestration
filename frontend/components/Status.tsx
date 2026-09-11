export function statusTone(status?: string): "ok" | "warn" | "danger" | "accent" | "" {
  const s = (status || "").toUpperCase();
  if (["CLOSED", "COMPLETED", "VERIFIED", "ACCEPTED", "DONE", "ACTIVE_OK"].includes(s)) return "ok";
  if (["PENDING", "IN_PROGRESS", "QUEUED", "CLARIFICATION", "WAITING", "DRAFT"].includes(s)) return "warn";
  if (["FAILED", "REJECTED", "BLOCKED", "OVERDUE", "ERROR"].includes(s)) return "danger";
  if (["AT_RISK", "REVIEW", "HUMAN_REVIEW"].includes(s)) return "accent";
  return "";
}

export function StatusBadge({ status }: { status?: string }) {
  const tone = statusTone(status);
  return <span className={`badge ${tone}`}>{status || "—"}</span>;
}

export function ReadinessBar({ value }: { value?: number | null }) {
  const pct = Math.max(0, Math.min(100, Number(value ?? 0)));
  const level = pct >= 80 ? "" : pct >= 40 ? "mid" : "low";
  return (
    <div className="readiness">
      <div className="muted" style={{ fontSize: "0.78rem", fontWeight: 600 }}>
        {pct}%
      </div>
      <div className="readiness-track">
        <div className={`readiness-fill ${level}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
