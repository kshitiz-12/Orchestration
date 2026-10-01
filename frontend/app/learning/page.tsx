"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

const CORRECTION_LABELS: Record<string, string> = {
  rerouted: "Sent to a different team",
  recategorised: "Request type changed",
  priority_changed: "Priority changed",
  detail_changed: "Details corrected",
  reassigned: "Reassigned to a person",
  reopened: "Reopened after closing",
};

function pct(v: number | null | undefined) {
  return v == null ? "—" : `${v}%`;
}

function tone(v: number | null | undefined) {
  if (v == null) return "";
  if (v >= 90) return "ok";
  if (v >= 70) return "warn";
  return "danger";
}

function label(v: string) {
  return v.replaceAll("_", " ");
}

function show(v: any) {
  if (Array.isArray(v)) return v.join(" or ");
  if (typeof v === "boolean") return v ? "approval needed" : "no approval";
  return v == null ? "—" : String(v);
}

function Metric({ title, value, note }: { title: string; value: number | null | undefined; note: string }) {
  return (
    <div className="panel">
      <div className="muted" style={{ fontSize: "0.78rem", fontWeight: 600 }}>{title}</div>
      <div style={{ fontSize: "1.6rem", fontWeight: 700, margin: "0.25rem 0" }}>
        <span className={`badge ${tone(value)}`} style={{ fontSize: "1.1rem" }}>{pct(value)}</span>
      </div>
      <div className="muted" style={{ fontSize: "0.78rem" }}>{note}</div>
    </div>
  );
}

export default function LearningPage() {
  const [data, setData] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [evalResult, setEvalResult] = useState<any>(null);
  const [edits, setEdits] = useState<Record<string, { title: string; content: string }>>({});

  function load() {
    api("/learning/summary")
      .then((d) => {
        setData(d);
        const next: Record<string, { title: string; content: string }> = {};
        for (const k of d.knowledge_drafts || []) next[k.entry_id] = { title: k.title, content: k.content };
        setEdits(next);
      })
      .catch((e) => setMsg(e.message));
  }

  useEffect(() => {
    load();
  }, []);

  async function act(key: string, path: string, body: any, done: string) {
    setBusy(key);
    setMsg("");
    try {
      await api(path, { method: "POST", body: JSON.stringify(body ?? {}) });
      setMsg(done);
      load();
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function runCheck() {
    setBusy("eval");
    setMsg("");
    try {
      const r = await api("/learning/eval/run", { method: "POST" });
      setEvalResult(r);
      load();
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setBusy(null);
    }
  }

  const acc = data?.accuracy;
  const overall = acc?.overall || {};
  const latest = evalResult || data?.last_eval;
  const drafts: any[] = data?.knowledge_drafts || [];
  const suggestions: any[] = (data?.suggestions || []).filter((s: any) => s.kind !== "knowledge");

  return (
    <AppShell
      title="AI learning"
      subtitle="How well the assistant reads requests, what admins keep correcting, and what it has learned. Nothing changes until you approve it."
      actions={
        <>
          <button className="btn secondary" onClick={load}>Refresh</button>
          <button className="btn accent" disabled={busy === "eval"} onClick={runCheck}>
            {busy === "eval" ? "Checking…" : "Run accuracy check"}
          </button>
        </>
      }
    >
      {msg && <p className="badge ok">{msg}</p>}
      {!data ? (
        <div className="panel empty">Loading…</div>
      ) : (
        <div className="stack">
          <div className="grid-4" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: "1rem" }}>
            <Metric title="Right request type" value={overall.type_accuracy_pct} note={`${overall.cases || 0} cases in the last ${acc?.window_days} days`} />
            <Metric title="Right team first time" value={overall.team_accuracy_pct} note="No admin had to re-route" />
            <Metric title="Right priority" value={overall.priority_accuracy_pct} note="No admin had to change it" />
            <Metric title="Handled without a person" value={data.automation?.automation_rate_pct} note={`Verified closures: ${pct(data.automation?.verified_closure_pct)}`} />
          </div>

          <div className="panel">
            <div className="panel-head">
              <div>
                <h3 style={{ marginBottom: "0.25rem" }}>Accuracy check</h3>
                <div className="muted" style={{ fontSize: "0.82rem" }}>
                  Replays {latest?.total ?? "a set of"} sample office emails and past verified cases through the AI. Run it after changing
                  instructions or office knowledge. No emails are sent and no cases are created.
                </div>
              </div>
              <span className="badge">Instruction version {data.prompt_version}</span>
            </div>
            {latest ? (
              <>
                <div className="chip-row" style={{ marginTop: "0.6rem" }}>
                  <span className={`badge ${tone(latest.score_pct)}`}>
                    {latest.passed}/{latest.total} fully correct ({pct(latest.score_pct)})
                  </span>
                  {Object.entries(latest.by_check || {}).map(([k, v]: [string, any]) => (
                    <span key={k} className={`badge ${tone(v.pct)}`}>
                      {k}: {v.passed}/{v.total}
                    </span>
                  ))}
                  <span className="badge">{latest.mode === "gemini" ? "Live AI" : "Rules only (AI unavailable)"}</span>
                  {latest.prompt_version && latest.prompt_version !== data.prompt_version && (
                    <span className="badge warn">Instructions changed since this run — run again</span>
                  )}
                </div>
                <div className="muted" style={{ fontSize: "0.78rem", marginTop: "0.4rem" }}>
                  Last run {new Date(latest.ran_at).toLocaleString()}
                </div>
                {(latest.failures || []).length > 0 && (
                  <table style={{ marginTop: "0.8rem" }}>
                    <thead>
                      <tr><th>Email</th><th>What went wrong</th><th>Source</th></tr>
                    </thead>
                    <tbody>
                      {latest.failures.map((f: any, i: number) => (
                        <tr key={i}>
                          <td style={{ maxWidth: 380 }}>{f.text}</td>
                          <td>
                            {f.failed.map((x: any) => (
                              <div key={x.check}>
                                <strong>{x.check}</strong>: expected {show(x.expected)}, got {show(x.got)}
                              </div>
                            ))}
                          </td>
                          <td>{f.source === "golden" ? "Sample" : "Past case"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </>
            ) : (
              <p className="muted">Not run yet.</p>
            )}
          </div>

          <div className="panel">
            <h3>Suggested rule changes</h3>
            <p className="muted" style={{ marginTop: 0, fontSize: "0.82rem" }}>
              When admins make the same correction again and again, it shows up here as a rule you can accept.
            </p>
            {suggestions.length === 0 ? (
              <p className="muted">No repeated corrections yet.</p>
            ) : (
              <div className="stack">
                {suggestions.map((s) => (
                  <div key={s.id} className="row" style={{ justifyContent: "space-between", alignItems: "flex-start", borderTop: "1px solid var(--line, #eee)", paddingTop: "0.6rem" }}>
                    <div>
                      <strong>{s.suggestion}</strong>
                      <div className="muted" style={{ fontSize: "0.8rem" }}>
                        {s.why} {s.cases?.length ? `· ${s.cases.slice(0, 5).join(", ")}` : ""}
                      </div>
                    </div>
                    {s.action?.type === "route_category" ? (
                      <button
                        className="btn accent"
                        disabled={busy === s.id}
                        onClick={() =>
                          act(s.id, "/learning/suggestions/apply", { category: s.action.category, department: s.action.department },
                            `New ${label(s.action.category)} requests will go to ${s.action.department}.`)
                        }
                      >
                        Apply rule
                      </button>
                    ) : (
                      <span className="badge">Review manually</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="panel">
            <h3>Learned answers waiting for approval</h3>
            <p className="muted" style={{ marginTop: 0, fontSize: "0.82rem" }}>
              When the AI didn&apos;t know an answer and an admin replied, that answer is saved here. Once approved, the AI uses it for
              future questions.
            </p>
            {drafts.length === 0 ? (
              <p className="muted">No new answers to review.</p>
            ) : (
              <div className="stack">
                {drafts.map((d) => {
                  const e = edits[d.entry_id] || { title: d.title, content: d.content };
                  const set = (patch: Partial<typeof e>) => setEdits({ ...edits, [d.entry_id]: { ...e, ...patch } });
                  return (
                    <div key={d.entry_id} className="field" style={{ borderTop: "1px solid var(--line, #eee)", paddingTop: "0.6rem" }}>
                      <input value={e.title} onChange={(ev) => set({ title: ev.target.value })} style={{ marginBottom: "0.4rem" }} />
                      <textarea rows={3} value={e.content} onChange={(ev) => set({ content: ev.target.value })} />
                      <div className="row" style={{ marginTop: "0.5rem" }}>
                        <button
                          className="btn accent"
                          disabled={busy === d.entry_id}
                          onClick={() => act(d.entry_id, `/learning/knowledge/${d.entry_id}/approve`, e, "Saved to office knowledge.")}
                        >
                          Approve
                        </button>
                        <button
                          className="btn danger"
                          disabled={busy === d.entry_id}
                          onClick={() => act(d.entry_id, `/learning/knowledge/${d.entry_id}/reject`, {}, "Discarded.")}
                        >
                          Discard
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="cols-2">
            <div className="panel">
              <h3>Accuracy by request type</h3>
              {(acc?.by_type || []).length === 0 ? (
                <p className="muted">No cases in this period yet.</p>
              ) : (
                <table>
                  <thead>
                    <tr><th>Type</th><th>Cases</th><th>Type</th><th>Team</th><th>Priority</th><th>Reopened</th></tr>
                  </thead>
                  <tbody>
                    {acc.by_type.map((r: any) => (
                      <tr key={r.type}>
                        <td>{label(r.type)}</td>
                        <td>{r.cases}</td>
                        <td><span className={`badge ${tone(r.type_accuracy_pct)}`}>{pct(r.type_accuracy_pct)}</span></td>
                        <td><span className={`badge ${tone(r.team_accuracy_pct)}`}>{pct(r.team_accuracy_pct)}</span></td>
                        <td><span className={`badge ${tone(r.priority_accuracy_pct)}`}>{pct(r.priority_accuracy_pct)}</span></td>
                        <td>{pct(r.reopen_rate_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div className="panel">
              <h3>What admins correct most</h3>
              {(acc?.correction_trend || []).length === 0 ? (
                <p className="muted">No corrections yet.</p>
              ) : (
                <table>
                  <tbody>
                    {acc.correction_trend.map((c: any) => (
                      <tr key={c.kind}>
                        <td>{CORRECTION_LABELS[c.kind] || label(c.kind)}</td>
                        <td style={{ textAlign: "right" }}><strong>{c.count}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="muted" style={{ fontSize: "0.78rem" }}>
                Admins correct a case by replying to its work-order email with &quot;change team to IT&quot;, &quot;change type to
                hvac&quot; or &quot;change priority to high&quot;.
              </p>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
