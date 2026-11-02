"use client";

import Link from "next/link";

export function AsKpi({
  label,
  value,
  hint,
  href,
  hot,
}: {
  label: string;
  value: string | number;
  hint?: string;
  href?: string;
  hot?: boolean;
}) {
  const inner = (
    <>
      <span className="label">{label}</span>
      <span className="value">{value}</span>
      {hint ? <span className="hint">{hint}</span> : null}
    </>
  );
  if (href) {
    return (
      <Link href={href} className={`as-kpi ${hot ? "hot" : ""}`}>
        {inner}
      </Link>
    );
  }
  return <div className={`as-kpi ${hot ? "hot" : ""}`}>{inner}</div>;
}

export function AsTabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="as-tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          className={value === t.id ? "on" : ""}
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function AsEmpty({ title, body, action }: { title: string; body?: string; action?: React.ReactNode }) {
  return (
    <div className="as-empty">
      <strong>{title}</strong>
      {body ? <p>{body}</p> : null}
      {action}
    </div>
  );
}

export function AsStatus({ status }: { status: string }) {
  const s = (status || "").toLowerCase();
  let cls = "neutral";
  if (/(active|ok|verified|done|closed|approved|complete)/.test(s)) cls = "ok";
  else if (/(pending|invited|review|wait|open|draft)/.test(s)) cls = "warn";
  else if (/(fail|suspend|black|reject|cancel|danger|past)/.test(s)) cls = "danger";
  return <span className={`as-status ${cls}`}>{status || "—"}</span>;
}
