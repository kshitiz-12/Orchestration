"use client";

import { AppShell } from "@/components/AppShell";
import { api, apiDownload, apiUpload } from "@/lib/api";
import { useEffect, useState } from "react";

type Dept = {
  department_id: string;
  code: string;
  name: string;
  categories: string[];
  primary_email: string | null;
  backup_emails: string[];
  approver_email: string | null;
  sla_hours: number;
  spend_approval_limit: number;
  is_active: boolean;
  needs_setup: boolean;
};

type Knowledge = { entry_id: string; key: string; section: string; title: string; content: string; is_active: boolean };

const TABS = [
  { id: "departments", label: "Departments" },
  { id: "knowledge", label: "Office knowledge" },
  { id: "import", label: "Import data" },
] as const;

const IMPORT_KINDS = [
  { id: "employees", label: "Employees", hint: "email, name, department, role, manager_email" },
  { id: "departments", label: "Departments", hint: "code, name, categories, primary_email, backup_emails, approver_email, sla_hours, spend_approval_limit" },
  { id: "resources", label: "Rooms, desks & parking", hint: "name, type (MEETING_ROOM / PARKING_SLOT / DESK / CABIN / LOCKER), capacity, floor, video_conferencing, display, near_department" },
  { id: "vendors", label: "Vendors", hint: "name, category, contact_email, location" },
  { id: "knowledge", label: "Policies & FAQs", hint: "key, section, title, content" },
];

const isPlaceholder = (email?: string | null) => !email || email.endsWith("@example.invalid");
const splitList = (s: string) => s.split(/[,;]/).map((x) => x.trim()).filter(Boolean);

export default function SetupPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("departments");
  const [status, setStatus] = useState<any>(null);
  const [msg, setMsg] = useState<{ text: string; tone: "ok" | "danger" } | null>(null);

  function loadStatus() {
    api("/setup/status").then(setStatus).catch((e) => setMsg({ text: e.message, tone: "danger" }));
  }

  useEffect(() => {
    loadStatus();
  }, []);

  const pending: string[] = status?.departments_needing_setup || [];

  return (
    <AppShell
      title="Company setup"
      subtitle="Department mailboxes, office knowledge the AI admin answers from, and bulk company data."
    >
      <div className="stack">
        <div className="grid kpis">
          <div className="kpi panel">
            <div className="muted">Main admin mailbox</div>
            <strong className="mono">{status?.admin_email || "not set"}</strong>
            <div className="muted" style={{ fontSize: "0.75rem" }}>Set in server env (ADMIN_OPS_EMAIL)</div>
          </div>
          <div className="kpi panel">
            <div className="muted">Departments</div>
            <strong>{status?.departments ?? "—"}</strong>
            {pending.length > 0 ? (
              <span className="badge warn">{pending.length} need a real email</span>
            ) : (
              status && <span className="badge ok">All set</span>
            )}
          </div>
          <div className="kpi panel">
            <div className="muted">Employees · Resources · Vendors</div>
            <strong>
              {status?.employees ?? "—"} · {status?.resources ?? "—"} · {status?.vendors ?? "—"}
            </strong>
          </div>
          <div className="kpi panel">
            <div className="muted">Knowledge entries · Open tickets</div>
            <strong>
              {status?.knowledge_entries ?? "—"} · {status?.open_tickets ?? "—"}
            </strong>
          </div>
        </div>

        {pending.length > 0 && (
          <div className="panel next-card tone-warn">
            <strong>Setup needed.</strong> Until a department has a real mailbox, its work orders go to the main admin
            mailbox instead: {pending.join(", ")}.
          </div>
        )}

        <div className="chip-row">
          {TABS.map((t) => (
            <button key={t.id} className={`btn ${tab === t.id ? "accent" : "secondary"}`} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>

        {msg && (
          <p className={`badge ${msg.tone}`} onClick={() => setMsg(null)} style={{ cursor: "pointer" }}>
            {msg.text}
          </p>
        )}

        {tab === "departments" && <Departments onChange={loadStatus} setMsg={setMsg} />}
        {tab === "knowledge" && <KnowledgeTab onChange={loadStatus} setMsg={setMsg} />}
        {tab === "import" && <ImportTab onChange={loadStatus} setMsg={setMsg} />}
      </div>
    </AppShell>
  );
}

type TabProps = { onChange: () => void; setMsg: (m: { text: string; tone: "ok" | "danger" } | null) => void };

function Departments({ onChange, setMsg }: TabProps) {
  const [rows, setRows] = useState<Dept[]>([]);
  const [editing, setEditing] = useState<Dept | null>(null);
  const [creating, setCreating] = useState(false);

  function load() {
    api<Dept[]>("/setup/departments").then(setRows).catch((e) => setMsg({ text: e.message, tone: "danger" }));
  }

  useEffect(() => {
    load();
  }, []);

  async function save(form: Record<string, any>) {
    try {
      if (creating) {
        await api("/setup/departments", { method: "POST", body: JSON.stringify(form) });
      } else if (editing) {
        await api(`/setup/departments/${editing.department_id}`, { method: "PATCH", body: JSON.stringify(form) });
      }
      setMsg({ text: `Saved ${form.name || editing?.name}`, tone: "ok" });
      setEditing(null);
      setCreating(false);
      load();
      onChange();
    } catch (e: any) {
      setMsg({ text: e.message, tone: "danger" });
    }
  }

  async function deactivate(d: Dept) {
    if (!window.confirm(`Deactivate ${d.name}? Its requests will go to the admin team.`)) return;
    try {
      await api(`/setup/departments/${d.department_id}`, { method: "DELETE" });
      load();
      onChange();
    } catch (e: any) {
      setMsg({ text: e.message, tone: "danger" });
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Departments</h2>
        <button className="btn accent" onClick={() => { setCreating(true); setEditing(null); }}>
          Add department
        </button>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        The AI admin routes each request to the department that handles its category. Work orders go to the primary
        and backup emails; spends above the limit need the approver.
      </p>
      {(creating || editing) && (
        <DeptForm
          dept={editing}
          onCancel={() => { setEditing(null); setCreating(false); }}
          onSave={save}
        />
      )}
      <table>
        <thead>
          <tr>
            <th>Department</th>
            <th>Handles</th>
            <th>Work orders to</th>
            <th>Approver</th>
            <th>SLA</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.department_id} style={{ opacity: d.is_active ? 1 : 0.5 }}>
              <td>
                <strong>{d.name}</strong>
                <div className="muted mono">{d.code}</div>
              </td>
              <td className="muted" style={{ maxWidth: 260, fontSize: "0.8rem" }}>{d.categories.join(", ")}</td>
              <td>
                {d.needs_setup ? (
                  <span className="badge warn">Setup needed</span>
                ) : (
                  <span className="mono">{[d.primary_email, ...d.backup_emails].filter((e) => !isPlaceholder(e)).join(", ")}</span>
                )}
              </td>
              <td className="mono">{isPlaceholder(d.approver_email) ? <span className="muted">main admin</span> : d.approver_email}</td>
              <td>{d.sla_hours}h</td>
              <td>
                <div className="row" style={{ gap: "0.4rem", justifyContent: "flex-end" }}>
                  <button className="btn secondary" onClick={() => { setEditing(d); setCreating(false); }}>Edit</button>
                  {d.is_active && d.code !== "ADMIN" && (
                    <button className="btn ghost" onClick={() => deactivate(d)}>Deactivate</button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DeptForm({ dept, onSave, onCancel }: { dept: Dept | null; onSave: (f: Record<string, any>) => void; onCancel: () => void }) {
  const clean = (e?: string | null) => (isPlaceholder(e) ? "" : e || "");
  const [code, setCode] = useState(dept?.code || "");
  const [name, setName] = useState(dept?.name || "");
  const [categories, setCategories] = useState((dept?.categories || []).join(", "));
  const [primary, setPrimary] = useState(clean(dept?.primary_email));
  const [backups, setBackups] = useState((dept?.backup_emails || []).filter((e) => !isPlaceholder(e)).join(", "));
  const [approver, setApprover] = useState(clean(dept?.approver_email));
  const [sla, setSla] = useState(String(dept?.sla_hours ?? 24));
  const [limit, setLimit] = useState(String(dept?.spend_approval_limit ?? 0));
  const [active, setActive] = useState(dept?.is_active ?? true);

  return (
    <div className="pre" style={{ marginBottom: "1rem", whiteSpace: "normal" }}>
      <div className="cols-2">
        {!dept && (
          <div className="field">
            <label>Code</label>
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="LEGAL" />
          </div>
        )}
        <div className="field">
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label>Primary email</label>
          <input value={primary} onChange={(e) => setPrimary(e.target.value)} placeholder="team@yourcompany.com" />
        </div>
        <div className="field">
          <label>Backup emails (comma separated)</label>
          <input value={backups} onChange={(e) => setBackups(e.target.value)} />
        </div>
        <div className="field">
          <label>Approver email (blank = main admin)</label>
          <input value={approver} onChange={(e) => setApprover(e.target.value)} />
        </div>
        <div className="field">
          <label>Request categories handled (comma separated)</label>
          <input value={categories} onChange={(e) => setCategories(e.target.value)} placeholder="maintenance, hvac" />
        </div>
        <div className="field">
          <label>SLA (hours)</label>
          <input type="number" min={1} value={sla} onChange={(e) => setSla(e.target.value)} />
        </div>
        <div className="field">
          <label>Spend needing approval above (INR, 0 = always)</label>
          <input type="number" min={0} value={limit} onChange={(e) => setLimit(e.target.value)} />
        </div>
      </div>
      {dept && (
        <label className="row" style={{ gap: "0.4rem", marginBottom: "0.75rem" }}>
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} /> Active
        </label>
      )}
      <div className="row">
        <button
          className="btn accent"
          onClick={() =>
            onSave({
              ...(dept ? {} : { code }),
              name,
              categories: splitList(categories),
              primary_email: primary,
              backup_emails: splitList(backups),
              approver_email: approver,
              sla_hours: Number(sla) || 24,
              spend_approval_limit: Number(limit) || 0,
              is_active: active,
            })
          }
        >
          Save
        </button>
        <button className="btn secondary" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function KnowledgeTab({ onChange, setMsg }: TabProps) {
  const [rows, setRows] = useState<Knowledge[]>([]);
  const [draft, setDraft] = useState<{ key: string; title: string; section: string; content: string } | null>(null);

  function load() {
    api<Knowledge[]>("/setup/knowledge").then(setRows).catch((e) => setMsg({ text: e.message, tone: "danger" }));
  }

  useEffect(() => {
    load();
  }, []);

  async function save() {
    if (!draft) return;
    try {
      await api("/setup/knowledge", { method: "PUT", body: JSON.stringify({ ...draft, key: draft.key || draft.title }) });
      setMsg({ text: `Saved "${draft.title}"`, tone: "ok" });
      setDraft(null);
      load();
      onChange();
    } catch (e: any) {
      setMsg({ text: e.message, tone: "danger" });
    }
  }

  async function remove(k: Knowledge) {
    if (!window.confirm(`Delete "${k.title}"?`)) return;
    await api(`/setup/knowledge/${k.entry_id}`, { method: "DELETE" }).catch((e) => setMsg({ text: e.message, tone: "danger" }));
    load();
    onChange();
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Office knowledge</h2>
        <button className="btn accent" onClick={() => setDraft({ key: "", title: "", section: "faq", content: "" })}>
          Add entry
        </button>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        Company profile, offices, policies and FAQs. The AI admin answers questions from this and never invents
        policy that isn&apos;t here. The sample entries are placeholders; replace them with your real details.
      </p>
      {draft && (
        <div className="pre" style={{ marginBottom: "1rem", whiteSpace: "normal" }}>
          <div className="cols-2">
            <div className="field">
              <label>Title</label>
              <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
            </div>
            <div className="field">
              <label>Section</label>
              <select value={draft.section} onChange={(e) => setDraft({ ...draft, section: e.target.value })}>
                {["company", "office", "policy", "faq"].map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div className="field">
            <label>Content</label>
            <textarea rows={6} value={draft.content} onChange={(e) => setDraft({ ...draft, content: e.target.value })} />
          </div>
          <div className="row">
            <button className="btn accent" onClick={save} disabled={!draft.title.trim() || !draft.content.trim()}>Save</button>
            <button className="btn secondary" onClick={() => setDraft(null)}>Cancel</button>
          </div>
        </div>
      )}
      <div className="stack">
        {rows.map((k) => (
          <div key={k.entry_id} className="pre" style={{ whiteSpace: "normal" }}>
            <div className="panel-head" style={{ marginBottom: "0.4rem" }}>
              <div>
                <strong>{k.title}</strong> <span className="badge">{k.section}</span>
              </div>
              <div className="row" style={{ gap: "0.4rem" }}>
                <button className="btn secondary" onClick={() => setDraft({ key: k.key, title: k.title, section: k.section, content: k.content })}>
                  Edit
                </button>
                <button className="btn ghost" onClick={() => remove(k)}>Delete</button>
              </div>
            </div>
            <div className="muted" style={{ whiteSpace: "pre-wrap" }}>{k.content}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ImportTab({ onChange, setMsg }: TabProps) {
  const [kind, setKind] = useState(IMPORT_KINDS[0].id);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const selected = IMPORT_KINDS.find((k) => k.id === kind)!;

  async function run(commit: boolean) {
    if (!file) return;
    setBusy(true);
    try {
      const res = await apiUpload(`/setup/import/${kind}?commit=${commit}`, file);
      setResult(res);
      if (commit) {
        setMsg({ text: `Imported ${res.new} new and updated ${res.updated} ${selected.label.toLowerCase()}`, tone: "ok" });
        onChange();
      }
    } catch (e: any) {
      setMsg({ text: e.message, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel">
      <h2>Import company data</h2>
      <p className="muted">
        Upload a CSV or Excel file. You&apos;ll see a preview first; nothing is saved until you confirm. Existing rows
        are matched by email, code, name or key and updated.
      </p>
      <div className="toolbar">
        <select className="select" value={kind} onChange={(e) => { setKind(e.target.value); setResult(null); }}>
          {IMPORT_KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
        </select>
        <button
          className="btn secondary"
          onClick={() => apiDownload(`/setup/templates/${kind}`, `${kind}_template.csv`).catch((e) => setMsg({ text: e.message, tone: "danger" }))}
        >
          Download template
        </button>
        <input
          type="file"
          accept=".csv,.xlsx,.xlsm"
          onChange={(e) => { setFile(e.target.files?.[0] || null); setResult(null); }}
        />
      </div>
      <div className="muted mono" style={{ marginBottom: "0.9rem" }}>Columns: {selected.hint}</div>
      <div className="row">
        <button className="btn secondary" disabled={!file || busy} onClick={() => run(false)}>Preview</button>
        <button
          className="btn accent"
          disabled={!file || busy || !result || result.committed || result.new + result.updated === 0}
          onClick={() => run(true)}
        >
          Confirm import
        </button>
      </div>

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <div className="row" style={{ marginBottom: "0.6rem" }}>
            <span className="badge accent">{result.total} rows</span>
            <span className="badge ok">{result.new} new</span>
            <span className="badge">{result.updated} updates</span>
            {result.errors.length > 0 && <span className="badge danger">{result.errors.length} with problems</span>}
            {result.committed && <span className="badge ok">Saved</span>}
          </div>
          {result.errors.length > 0 && (
            <div className="pre" style={{ marginBottom: "0.6rem" }}>
              {result.errors.map((e: any) => `Row ${e.row}: ${e.error}`).join("\n")}
            </div>
          )}
          <table>
            <thead>
              <tr><th>Row</th><th>Action</th><th>Item</th></tr>
            </thead>
            <tbody>
              {result.preview.map((p: any) => (
                <tr key={p.row}>
                  <td>{p.row}</td>
                  <td><span className={`badge ${p.action === "new" ? "ok" : ""}`}>{p.action}</span></td>
                  <td>{p.item}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
