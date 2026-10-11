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
  handover_info?: string | null;
  location_id?: string | null;
  location_name?: string | null;
  is_active: boolean;
  needs_setup: boolean;
};

type Place = {
  location_id: string;
  code: string | null;
  name: string;
  type: string;
  parent_id: string | null;
  aliases: string;
  path: string;
  teams: number;
  people: number;
  children: number;
};

type PlaceList = { total: number; items: Place[]; types: string[] };

type Knowledge = { entry_id: string; key: string; section: string; title: string; content: string; is_active: boolean };

type SiteService = {
  service_id: string;
  site: string;
  code: string;
  name: string;
  delivery_model: string;
  provider: string | null;
  owner_department: string;
  unit: string;
  rate: number;
  included_limit: number;
  premium_triggers: string[];
  premium_rate: number;
  is_active: boolean;
};

type CostCentre = {
  cost_centre_id: string;
  code: string;
  name: string;
  department: string | null;
  approver_name: string | null;
  approver_email: string | null;
  is_active: boolean;
  needs_setup: boolean;
};

const TABS = [
  { id: "import", label: "Upload Excel" },
  { id: "places", label: "Offices" },
  { id: "departments", label: "Teams" },
  { id: "services", label: "Site services" },
  { id: "cost_centres", label: "Cost centres" },
  { id: "knowledge", label: "Policies & FAQs" },
] as const;

const DELIVERY_MODELS = ["INCLUDED", "CONTRACT", "SUBSIDISED", "CHARGEABLE", "OUTSOURCED"];

const IMPORT_KINDS = [
  { id: "locations", label: "Offices", hint: "code, name, type (REGION / CITY / BRANCH / BUILDING / FLOOR ...), parent_code, aliases" },
  { id: "employees", label: "Employees", hint: "email, name, department, role, manager_email, location (place code or name)" },
  { id: "departments", label: "Teams", hint: "code, name, categories, primary_email, backup_emails, approver_email, sla_hours, spend_approval_limit, location (blank = whole company)" },
  { id: "resources", label: "Rooms, desks & parking", hint: "name, type (MEETING_ROOM / PARKING_SLOT / DESK / CABIN / LOCKER), capacity, floor, video_conferencing, display, near_department" },
  { id: "vendors", label: "Vendors", hint: "name, category, contact_email, location" },
  { id: "knowledge", label: "Policies & FAQs", hint: "key, section, title, content" },
  { id: "site_services", label: "Site services", hint: "site, code, name, delivery_model (INCLUDED / CONTRACT / SUBSIDISED / CHARGEABLE / OUTSOURCED), owner_department, unit, rate, included_limit, premium_triggers, premium_rate, provider" },
  { id: "cost_centres", label: "Cost centres", hint: "code, name, department, approver_name, approver_email" },
];

const isPlaceholder = (email?: string | null) => !email || email.endsWith("@example.invalid");
const splitList = (s: string) => s.split(/[,;]/).map((x) => x.trim()).filter(Boolean);

function usePlaces(setMsg: TabProps["setMsg"]) {
  const [places, setPlaces] = useState<PlaceList>({ total: 0, items: [], types: [] });
  function load() {
    api<PlaceList>("/setup/locations?limit=5000").then(setPlaces).catch((e) => setMsg({ text: e.message, tone: "danger" }));
  }
  useEffect(() => {
    load();
  }, []);
  return { places, reload: load };
}

export default function SetupPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("import");
  const [status, setStatus] = useState<any>(null);
  const [msg, setMsg] = useState<{ text: string; tone: "ok" | "danger" } | null>(null);

  function loadStatus() {
    api("/setup/status").then(setStatus).catch((e) => setMsg({ text: e.message, tone: "danger" }));
  }

  useEffect(() => {
    loadStatus();
  }, []);

  const pending: string[] = status?.departments_needing_setup || [];
  const employees = Number(status?.employees || 0);
  const locations = Number(status?.locations || 0);

  return (
    <AppShell
      title="Company data"
      subtitle="Load offices, teams, and people once — then Desk can route every employee request to the right branch."
    >
      <div className="stack">
        <div className="grid kpis">
          <div className="kpi">
            <div className="label">Offices</div>
            <div className="value">{locations || "0"}</div>
            <div className="hint">Branches & buildings on file</div>
          </div>
          <div className="kpi">
            <div className="label">Teams</div>
            <div className="value">{status?.departments ?? "0"}</div>
            <div className="hint">
              {pending.length > 0 ? (
                <span className="badge warn">{pending.length} need a work email</span>
              ) : status ? (
                <span className="badge ok">Mailboxes ready</span>
              ) : (
                "—"
              )}
            </div>
          </div>
          <div className="kpi">
            <div className="label">Employees</div>
            <div className="value">{employees || "0"}</div>
            <div className="hint">Only these people get replies</div>
          </div>
          <div className="kpi">
            <div className="label">Open requests</div>
            <div className="value">{status?.open_tickets ?? "0"}</div>
            <div className="hint">{status?.resources ?? 0} rooms & assets</div>
          </div>
        </div>

        {pending.length > 0 && (
          <div className="next-card tone-warn">
            <strong>Some teams still need a real work email</strong>
            <span>
              Until then, their work goes to the main admin mailbox: {pending.join(", ")}.
            </span>
          </div>
        )}

        {employees <= 1 && (
          <div className="setup-hero">
            <div>
              <h2>Start with one Excel upload</h2>
              <p>
                Download the company template, fill offices / teams / employees, then Preview and Confirm.
                You can edit individual rows later under Offices and Teams.
              </p>
            </div>
            <div className="row">
              <button className="btn accent" type="button" onClick={() => setTab("import")}>
                Go to Upload Excel
              </button>
            </div>
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

        {tab === "import" && <ImportTab onChange={loadStatus} setMsg={setMsg} />}
        {tab === "places" && <PlacesTab onChange={loadStatus} setMsg={setMsg} />}
        {tab === "departments" && <Departments onChange={loadStatus} setMsg={setMsg} />}
        {tab === "services" && <ServicesTab onChange={loadStatus} setMsg={setMsg} />}
        {tab === "cost_centres" && <CostCentresTab onChange={loadStatus} setMsg={setMsg} />}
        {tab === "knowledge" && <KnowledgeTab onChange={loadStatus} setMsg={setMsg} />}
      </div>
    </AppShell>
  );
}

type TabProps = { onChange: () => void; setMsg: (m: { text: string; tone: "ok" | "danger" } | null) => void };

function PlacesTab({ onChange, setMsg }: TabProps) {
  const { places, reload } = usePlaces(setMsg);
  const [q, setQ] = useState("");
  const [draft, setDraft] = useState<Record<string, any> | null>(null);
  const shown = places.items.filter((p) =>
    `${p.code || ""} ${p.name} ${p.aliases} ${p.path}`.toLowerCase().includes(q.trim().toLowerCase()),
  );

  async function save() {
    if (!draft) return;
    const body = { name: draft.name, code: draft.code, type: draft.type, parent_id: draft.parent_id || "", aliases: draft.aliases };
    try {
      if (draft.location_id) {
        await api(`/setup/locations/${draft.location_id}`, { method: "PATCH", body: JSON.stringify(body) });
      } else {
        await api("/setup/locations", { method: "POST", body: JSON.stringify(body) });
      }
      setMsg({ text: `Saved ${draft.name}`, tone: "ok" });
      setDraft(null);
      reload();
      onChange();
    } catch (e: any) {
      setMsg({ text: e.message, tone: "danger" });
    }
  }

  async function remove(p: Place) {
    if (!window.confirm(`Delete ${p.name}?`)) return;
    try {
      await api(`/setup/locations/${p.location_id}`, { method: "DELETE" });
      reload();
      onChange();
    } catch (e: any) {
      setMsg({ text: e.message, tone: "danger" });
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Branches &amp; places</h2>
        <button
          className="btn accent"
          onClick={() => setDraft({ name: "", code: "", type: "BRANCH", parent_id: "", aliases: "" })}
        >
          Add place
        </button>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        Regions, cities, branches, and buildings. A team on a city covers every branch underneath unless you override
        it. Prefer Upload Excel when you have many sites.
      </p>
      {draft && (
        <div className="pre" style={{ marginBottom: "1rem", whiteSpace: "normal" }}>
          <div className="cols-2">
            <div className="field">
              <label>Name</label>
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Pune Hinjewadi" />
            </div>
            <div className="field">
              <label>Code</label>
              <input value={draft.code || ""} onChange={(e) => setDraft({ ...draft, code: e.target.value })} placeholder="PUN-HJ" />
            </div>
            <div className="field">
              <label>Type</label>
              <select value={draft.type} onChange={(e) => setDraft({ ...draft, type: e.target.value })}>
                {(places.types.length ? places.types : ["REGION", "CITY", "BRANCH", "BUILDING", "FLOOR"]).map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label>Inside</label>
              <select value={draft.parent_id || ""} onChange={(e) => setDraft({ ...draft, parent_id: e.target.value })}>
                <option value="">— top level —</option>
                {places.items
                  .filter((p) => p.location_id !== draft.location_id)
                  .map((p) => (
                    <option key={p.location_id} value={p.location_id}>{p.path}</option>
                  ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label>Other names people use (separated by ;)</label>
            <input value={draft.aliases || ""} onChange={(e) => setDraft({ ...draft, aliases: e.target.value })} placeholder="Hinjewadi; Pune office" />
          </div>
          <div className="row">
            <button className="btn accent" onClick={save} disabled={!draft.name?.trim()}>Save</button>
            <button className="btn secondary" onClick={() => setDraft(null)}>Cancel</button>
          </div>
        </div>
      )}
      <div className="toolbar">
        <input className="select" placeholder="Search places" value={q} onChange={(e) => setQ(e.target.value)} />
        <span className="muted">{shown.length} of {places.total}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>Place</th>
            <th>Type</th>
            <th>Also called</th>
            <th>Teams</th>
            <th>People</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {shown.slice(0, 300).map((p) => (
            <tr key={p.location_id}>
              <td>
                <strong>{p.path}</strong>
                {p.code && <div className="muted mono">{p.code}</div>}
              </td>
              <td><span className="badge">{p.type.toLowerCase()}</span></td>
              <td className="muted" style={{ fontSize: "0.8rem" }}>{p.aliases || "—"}</td>
              <td>{p.teams || <span className="muted">from above</span>}</td>
              <td>{p.people}</td>
              <td>
                <div className="row" style={{ gap: "0.4rem", justifyContent: "flex-end" }}>
                  <button className="btn secondary" onClick={() => setDraft({ ...p })}>Edit</button>
                  {!p.teams && !p.people && !p.children && (
                    <button className="btn ghost" onClick={() => remove(p)}>Delete</button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {shown.length > 300 && <p className="muted">Showing the first 300 — search to narrow down.</p>}
    </div>
  );
}

function Departments({ onChange, setMsg }: TabProps) {
  const [rows, setRows] = useState<Dept[]>([]);
  const [editing, setEditing] = useState<Dept | null>(null);
  const [creating, setCreating] = useState(false);
  const [q, setQ] = useState("");
  const { places } = usePlaces(setMsg);
  const shown = rows.filter((d) =>
    `${d.code} ${d.name} ${d.categories.join(" ")} ${d.location_name || "whole company"}`
      .toLowerCase()
      .includes(q.trim().toLowerCase()),
  );

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
        Desk routes each request to the team that handles its category, at the employee&apos;s branch.
        A team set to cover a branch, city or region takes that place&apos;s work; teams covering the whole company take
        everything else. Name branch teams after the main team (FACILITIES_PUNE, ADMIN_PUNE): an ADMIN_ team is that
        branch&apos;s admin and gets its approvals and alerts. Spends above the limit need the approver.
      </p>
      {(creating || editing) && (
        <DeptForm
          dept={editing}
          places={places.items}
          onCancel={() => { setEditing(null); setCreating(false); }}
          onSave={save}
        />
      )}
      <div className="toolbar">
        <input className="select" placeholder="Search teams or branches" value={q} onChange={(e) => setQ(e.target.value)} />
        <span className="muted">{shown.length} of {rows.length}</span>
      </div>
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
          {shown.map((d) => (
            <tr key={d.department_id} style={{ opacity: d.is_active ? 1 : 0.5 }}>
              <td>
                <strong>{d.name}</strong>
                <div className="muted mono">{d.code}</div>
                <div className="muted" style={{ fontSize: "0.75rem" }}>Covers: {d.location_name || "whole company"}</div>
                {d.handover_info && (
                  <div className="muted" style={{ fontSize: "0.75rem", maxWidth: 220 }}>Collect: {d.handover_info}</div>
                )}
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

function DeptForm({
  dept,
  places,
  onSave,
  onCancel,
}: {
  dept: Dept | null;
  places: Place[];
  onSave: (f: Record<string, any>) => void;
  onCancel: () => void;
}) {
  const clean = (e?: string | null) => (isPlaceholder(e) ? "" : e || "");
  const [locationId, setLocationId] = useState(dept?.location_id || "");
  const [code, setCode] = useState(dept?.code || "");
  const [name, setName] = useState(dept?.name || "");
  const [categories, setCategories] = useState((dept?.categories || []).join(", "));
  const [primary, setPrimary] = useState(clean(dept?.primary_email));
  const [backups, setBackups] = useState((dept?.backup_emails || []).filter((e) => !isPlaceholder(e)).join(", "));
  const [approver, setApprover] = useState(clean(dept?.approver_email));
  const [sla, setSla] = useState(String(dept?.sla_hours ?? 24));
  const [limit, setLimit] = useState(String(dept?.spend_approval_limit ?? 0));
  const [handover, setHandover] = useState(dept?.handover_info || "");
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
          <label>Covers</label>
          <select value={locationId} onChange={(e) => setLocationId(e.target.value)}>
            <option value="">Whole company</option>
            {places.map((p) => (
              <option key={p.location_id} value={p.location_id}>{p.path}</option>
            ))}
          </select>
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
      <div className="field">
        <label>Where to collect (shared with requesters when their item is ready)</label>
        <input
          value={handover}
          onChange={(e) => setHandover(e.target.value)}
          placeholder="IT desk, 3rd floor, 10 AM - 6 PM, ask for Rahul"
        />
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
              handover_info: handover,
              location_id: locationId,
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

function ServicesTab({ onChange, setMsg }: TabProps) {
  const [rows, setRows] = useState<SiteService[]>([]);
  const [draft, setDraft] = useState<Record<string, any> | null>(null);

  function load() {
    api<SiteService[]>("/setup/site-services").then(setRows).catch((e) => setMsg({ text: e.message, tone: "danger" }));
  }

  useEffect(() => {
    load();
  }, []);

  async function save() {
    if (!draft) return;
    try {
      await api("/setup/site-services", {
        method: "PUT",
        body: JSON.stringify({
          ...draft,
          rate: Number(draft.rate) || 0,
          included_limit: Number(draft.included_limit) || 0,
          premium_rate: Number(draft.premium_rate) || 0,
          premium_triggers: splitList(draft.premium_triggers || ""),
        }),
      });
      setMsg({ text: `Saved ${draft.name || draft.code}`, tone: "ok" });
      setDraft(null);
      load();
      onChange();
    } catch (e: any) {
      setMsg({ text: e.message, tone: "danger" });
    }
  }

  const edit = (s?: SiteService) =>
    setDraft(
      s
        ? { ...s, premium_triggers: (s.premium_triggers || []).join(", "), existing: true }
        : { site: "Corporate Office", code: "", name: "", delivery_model: "INCLUDED", owner_department: "ADMIN", unit: "per_event", rate: 0, included_limit: 0, premium_triggers: "", premium_rate: 0, provider: "" },
    );

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Site services &amp; charges</h2>
        <button className="btn accent" onClick={() => edit()}>Add service</button>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        How each service is delivered at your site. Included services go ahead with no approval; only subsidised,
        chargeable or outsourced items (or included items asked for as premium) need cost approval. The sample
        rows are placeholders — replace them with your real rates.
      </p>
      {draft && (
        <div className="pre" style={{ marginBottom: "1rem", whiteSpace: "normal" }}>
          <div className="cols-2">
            {!draft.existing && (
              <div className="field">
                <label>Code</label>
                <input value={draft.code} onChange={(e) => setDraft({ ...draft, code: e.target.value })} placeholder="high_tea" />
              </div>
            )}
            <div className="field">
              <label>Name</label>
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            </div>
            <div className="field">
              <label>Delivery model</label>
              <select value={draft.delivery_model} onChange={(e) => setDraft({ ...draft, delivery_model: e.target.value })}>
                {DELIVERY_MODELS.map((m) => <option key={m}>{m}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Delivered by (department code)</label>
              <input value={draft.owner_department} onChange={(e) => setDraft({ ...draft, owner_department: e.target.value })} placeholder="CAFETERIA" />
            </div>
            <div className="field">
              <label>Unit</label>
              <select value={draft.unit} onChange={(e) => setDraft({ ...draft, unit: e.target.value })}>
                {["per_event", "per_person", "per_trip", "per_night", "per_slot"].map((u) => <option key={u}>{u}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Rate (INR per unit)</label>
              <input type="number" min={0} value={draft.rate} onChange={(e) => setDraft({ ...draft, rate: e.target.value })} />
            </div>
            <div className="field">
              <label>Free quantity before charges apply</label>
              <input type="number" min={0} value={draft.included_limit} onChange={(e) => setDraft({ ...draft, included_limit: e.target.value })} />
            </div>
            <div className="field">
              <label>Premium words (make an included item chargeable)</label>
              <input value={draft.premium_triggers} onChange={(e) => setDraft({ ...draft, premium_triggers: e.target.value })} placeholder="premium, staffed, branded" />
            </div>
            <div className="field">
              <label>Premium rate (INR)</label>
              <input type="number" min={0} value={draft.premium_rate} onChange={(e) => setDraft({ ...draft, premium_rate: e.target.value })} />
            </div>
            <div className="field">
              <label>Provider</label>
              <input value={draft.provider || ""} onChange={(e) => setDraft({ ...draft, provider: e.target.value })} />
            </div>
          </div>
          <div className="row">
            <button className="btn accent" onClick={save} disabled={!draft.name?.trim() || !draft.code?.trim()}>Save</button>
            <button className="btn secondary" onClick={() => setDraft(null)}>Cancel</button>
          </div>
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>Service</th>
            <th>Model</th>
            <th>Delivered by</th>
            <th>Rate</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.service_id} style={{ opacity: s.is_active ? 1 : 0.5 }}>
              <td>
                <strong>{s.name}</strong>
                <div className="muted mono">{s.code} · {s.site}</div>
              </td>
              <td>
                <span className={`badge ${s.delivery_model === "INCLUDED" || s.delivery_model === "CONTRACT" ? "ok" : "warn"}`}>
                  {s.delivery_model.toLowerCase()}
                </span>
              </td>
              <td className="mono">{s.owner_department}</td>
              <td className="muted" style={{ fontSize: "0.85rem" }}>
                {s.rate ? `₹${s.rate} ${s.unit.replace("_", " ")}` : "—"}
                {s.premium_triggers?.length ? <div>premium ₹{s.premium_rate || "quote"}: {s.premium_triggers.slice(0, 3).join(", ")}</div> : null}
              </td>
              <td>
                <button className="btn secondary" onClick={() => edit(s)}>Edit</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CostCentresTab({ onChange, setMsg }: TabProps) {
  const [rows, setRows] = useState<CostCentre[]>([]);
  const [draft, setDraft] = useState<Record<string, any> | null>(null);

  function load() {
    api<CostCentre[]>("/setup/cost-centres").then(setRows).catch((e) => setMsg({ text: e.message, tone: "danger" }));
  }

  useEffect(() => {
    load();
  }, []);

  async function save() {
    if (!draft) return;
    try {
      await api("/setup/cost-centres", { method: "PUT", body: JSON.stringify(draft) });
      setMsg({ text: `Saved ${draft.code}`, tone: "ok" });
      setDraft(null);
      load();
      onChange();
    } catch (e: any) {
      setMsg({ text: e.message, tone: "danger" });
    }
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Cost centres</h2>
        <button className="btn accent" onClick={() => setDraft({ code: "", name: "", department: "", approver_name: "", approver_email: "" })}>
          Add cost centre
        </button>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        Chargeable event costs are booked to the requester&apos;s cost centre (matched by their department, or the code
        they quote). The approver gets the cost approval mail along with the managers; without one, the managers and
        main admin approve.
      </p>
      {draft && (
        <div className="pre" style={{ marginBottom: "1rem", whiteSpace: "normal" }}>
          <div className="cols-2">
            <div className="field">
              <label>Code</label>
              <input value={draft.code} onChange={(e) => setDraft({ ...draft, code: e.target.value })} placeholder="SL-1101" disabled={!!draft.existing} />
            </div>
            <div className="field">
              <label>Name</label>
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            </div>
            <div className="field">
              <label>Employee department</label>
              <input value={draft.department || ""} onChange={(e) => setDraft({ ...draft, department: e.target.value })} placeholder="Sales" />
            </div>
            <div className="field">
              <label>Approver name</label>
              <input value={draft.approver_name || ""} onChange={(e) => setDraft({ ...draft, approver_name: e.target.value })} />
            </div>
            <div className="field">
              <label>Approver email</label>
              <input value={draft.approver_email || ""} onChange={(e) => setDraft({ ...draft, approver_email: e.target.value })} />
            </div>
          </div>
          <div className="row">
            <button className="btn accent" onClick={save} disabled={!draft.code?.trim() || !draft.name?.trim()}>Save</button>
            <button className="btn secondary" onClick={() => setDraft(null)}>Cancel</button>
          </div>
        </div>
      )}
      <table>
        <thead>
          <tr>
            <th>Cost centre</th>
            <th>Department</th>
            <th>Approver</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.cost_centre_id} style={{ opacity: c.is_active ? 1 : 0.5 }}>
              <td>
                <strong>{c.name}</strong>
                <div className="muted mono">{c.code}</div>
              </td>
              <td>{c.department || <span className="muted">—</span>}</td>
              <td>
                {c.approver_name || ""}{" "}
                {c.needs_setup ? <span className="badge warn">no email yet</span> : <span className="mono muted">{c.approver_email}</span>}
              </td>
              <td>
                <button
                  className="btn secondary"
                  onClick={() => setDraft({ ...c, approver_email: c.needs_setup ? "" : c.approver_email, existing: true })}
                >
                  Edit
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
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
        Company profile, offices, policies and FAQs. Desk answers employee questions from this and does not invent
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
  const [mode, setMode] = useState<"company" | "single">("company");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const selected = IMPORT_KINDS.find((k) => k.id === kind)!;

  async function run(commit: boolean) {
    if (!file) return;
    setBusy(true);
    try {
      const path =
        mode === "company"
          ? `/setup/import/company?commit=${commit}`
          : `/setup/import/${kind}?commit=${commit}`;
      const res = await apiUpload(path, file);
      setResult(res);
      if (commit) {
        const label = mode === "company" ? "company rows" : selected.label.toLowerCase();
        setMsg({ text: `Imported ${res.new} new and updated ${res.updated} ${label}`, tone: "ok" });
        onChange();
      }
    } catch (e: any) {
      setMsg({ text: e.message, tone: "danger" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <div className="panel">
        <h2>Upload company Excel</h2>
        <p className="muted">
          Use the multi-sheet workbook (offices, teams, employees, rooms). Or drop any structured Excel / CSV —
          Desk maps it, shows a preview, and saves only when you confirm.
        </p>
        <div className="toolbar">
          <button
            className={`btn ${mode === "company" ? "accent" : "secondary"}`}
            onClick={() => { setMode("company"); setResult(null); }}
          >
            Full company file
          </button>
          <button
            className={`btn ${mode === "single" ? "accent" : "secondary"}`}
            onClick={() => { setMode("single"); setResult(null); }}
          >
            One sheet only
          </button>
          {mode === "company" && (
            <button
              className="btn secondary"
              onClick={() =>
                apiDownload("/setup/templates/company", "company_template.xlsx").catch((e) =>
                  setMsg({ text: e.message, tone: "danger" })
                )
              }
            >
              Download Excel template
            </button>
          )}
        </div>
        {mode === "company" ? (
          <>
            <div className="muted" style={{ marginBottom: "0.9rem", lineHeight: 1.5 }}>
              Include sheets for offices, teams, employees, rooms & assets, vendors, policies, site services, and cost centres as needed.
            </div>
            <input
              type="file"
              accept=".csv,.xlsx,.xlsm,.json,.txt"
              onChange={(e) => {
                setFile(e.target.files?.[0] || null);
                setResult(null);
              }}
            />
          </>
        ) : (
          <>
            <div className="toolbar" style={{ marginTop: "0.75rem" }}>
              <select
                className="select"
                value={kind}
                onChange={(e) => {
                  setKind(e.target.value);
                  setResult(null);
                }}
              >
                {IMPORT_KINDS.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.label}
                  </option>
                ))}
              </select>
              <button
                className="btn secondary"
                onClick={() =>
                  apiDownload(`/setup/templates/${kind}`, `${kind}_template.csv`).catch((e) =>
                    setMsg({ text: e.message, tone: "danger" })
                  )
                }
              >
                Download template
              </button>
              <input
                type="file"
                accept=".csv,.xlsx,.xlsm"
                onChange={(e) => {
                  setFile(e.target.files?.[0] || null);
                  setResult(null);
                }}
              />
            </div>
            <div className="muted mono" style={{ marginBottom: "0.9rem" }}>
              Columns: {selected.hint}
            </div>
          </>
        )}
        <div className="row" style={{ marginTop: "0.75rem" }}>
          <button className="btn secondary" disabled={!file || busy} onClick={() => run(false)}>
            {busy ? "Working…" : "Preview"}
          </button>
          <button
            className="btn accent"
            disabled={!file || busy || (result?.committed === true)}
            onClick={() => {
              if (
                !result &&
                !window.confirm(
                  "Import and save this file now? Large company files can take a few minutes."
                )
              ) {
                return;
              }
              run(true);
            }}
          >
            {busy ? "Importing…" : "Import & save"}
          </button>
        </div>
        <p className="muted" style={{ marginTop: "0.65rem", fontSize: "0.82rem" }}>
          Large files (hundreds of employees) — use Import &amp; save directly. Preview can time out on the free API.
        </p>

        {result && (
          <div style={{ marginTop: "1rem" }}>
            <div className="row" style={{ marginBottom: "0.6rem" }}>
              <span className="badge accent">{result.total} rows</span>
              <span className="badge ok">{result.new} new</span>
              <span className="badge">{result.updated} updates</span>
              {result.source && <span className="badge">{result.source}</span>}
              {result.kinds && <span className="badge">{result.kinds.join(", ")}</span>}
              {result.errors?.length > 0 && (
                <span className="badge danger">{result.errors.length} with problems</span>
              )}
              {result.committed && <span className="badge ok">Saved</span>}
            </div>
            {result.errors?.length > 0 && (
              <div className="pre" style={{ marginBottom: "0.6rem" }}>
                {result.errors
                  .map((e: any) => `${e.kind ? e.kind + " " : ""}Row ${e.row}: ${e.error}`)
                  .join("\n")}
              </div>
            )}
            <table>
              <thead>
                <tr>
                  {mode === "company" && <th>Kind</th>}
                  <th>Row</th>
                  <th>Action</th>
                  <th>Item</th>
                </tr>
              </thead>
              <tbody>
                {(result.preview || []).map((p: any, i: number) => (
                  <tr key={`${p.kind || ""}-${p.row}-${i}`}>
                    {mode === "company" && <td className="mono">{p.kind || ""}</td>}
                    <td>{p.row}</td>
                    <td>
                      <span className={`badge ${p.action === "new" ? "ok" : ""}`}>{p.action}</span>
                    </td>
                    <td>{p.item}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
