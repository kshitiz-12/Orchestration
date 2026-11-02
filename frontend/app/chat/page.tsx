"use client";

import { AppShell } from "@/components/AppShell";
import { rememberUploadLocally, uploadFigures } from "@/components/UploadMeter";
import { api, apiUpload } from "@/lib/api";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

type Bubble = { role: "user" | "desk"; text: string };

const KIND_WORDS: Record<string, string> = {
  locations: "offices",
  employees: "people",
  departments: "teams",
  vendors: "vendors",
  stock: "stock items",
  resources: "rooms",
  site_services: "services",
  knowledge: "policies",
  cost_centres: "cost centres",
};

function describeImport(filename: string, saved: any) {
  const kinds: string[] = Array.isArray(saved?.kinds) ? saved.kinds : [];
  const words = kinds.map((k) => KIND_WORDS[k] || k);
  const what = words.length ? words.join(", ") : "company rows";
  const added = Number(saved?.new || 0);
  const refreshed = Number(saved?.updated || 0);
  let reply = `${filename || "This file"} is ${what}. I added ${added}. ${refreshed} were already on file and were refreshed.`;
  if (!kinds.includes("locations") && !kinds.includes("employees")) {
    reply += " Offices and people stay as they are, because this file does not list them. Part 1 is the offices and contacts file.";
  }
  return reply;
}

function answerFromScreen(message: string, facts: { openCases: number; waitingYou: number; pastSla: number; employees: number; locations: number; percent: number; saved: number; total: number; last?: string }) {
  const text = message.toLowerCase();
  if (/updat|why|haven|hasn|didn|change|still|same/.test(text)) {
    if (facts.last) return facts.last;
    if (facts.total) {
      return `The last Excel saved ${facts.saved} of ${facts.total} rows (${facts.percent}%). Offices are still ${facts.locations} and people are ${facts.employees}, because that file did not list them. Part 1 is the offices and contacts file.`;
    }
  }
  if (/office|branch|location|campus/.test(text)) {
    return `There are ${facts.locations} offices on file, and ${facts.employees} people.`;
  }
  if (/people|employee|staff/.test(text)) {
    return `${facts.employees} people are on file across ${facts.locations} offices.`;
  }
  if (/open|request|past due|decision|waiting/.test(text)) {
    return `${facts.openCases} requests are open. ${facts.waitingYou} need your decision. ${facts.pastSla} are past due.`;
  }
  if (/excel|upload|percent/.test(text)) {
    return facts.total
      ? `${facts.percent}% of the last Excel is saved (${facts.saved} of ${facts.total} rows).`
      : "No Excel file has been saved yet. Drop one in this chat.";
  }
  return "Ask about offices, people, open requests, or the Excel upload. Or drop a workbook here and I will save what it contains.";
}

const WELCOME =
  "Ask about offices, people, vendors, stock, rooms, or open requests. Drop an Excel file here and I will read what it is and save what belongs in the company records.";

export default function HomePage() {
  const [kpis, setKpis] = useState<any>(null);
  const [setup, setSetup] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<Bubble[]>([{ role: "desk", text: WELCOME }]);
  const [draft, setDraft] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [readingFile, setReadingFile] = useState(false);
  const [sent, setSent] = useState(0);
  const [lastImport, setLastImport] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [k, s] = await Promise.all([api("/dashboard/kpis"), api("/setup/status").catch(() => null)]);
      setKpis(k && typeof k === "object" ? k : null);
      setSetup(s);
    } catch (e: any) {
      setError(e.message || "Could not load");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages, sending]);

  const waitingYou =
    kpis?.waiting_on_you != null
      ? Number(kpis.waiting_on_you)
      : Number(kpis?.human_reviews || 0) + Number(kpis?.pending_approvals || 0) + Number(kpis?.pending_confirmations || 0);
  const openCases = Number(kpis?.outcomes_active || 0);
  const pastSla = Number(kpis?.past_sla || 0);
  const employees = Number(setup?.employees || 0);
  const locations = Number(setup?.locations || 0);
  const upload = uploadFigures(setup?.excel_upload);

  async function onSend(e?: FormEvent) {
    e?.preventDefault();
    const text = draft.trim();
    if (sending || (!text && !file)) return;
    const history = messages
      .filter((m) => m.text !== WELCOME)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.text }));
    const attached = file;
    setMessages((prev) => [
      ...prev,
      { role: "user", text: [text, attached ? `File: ${attached.name}` : ""].filter(Boolean).join("\n") },
    ]);
    setDraft("");
    setFile(null);
    setReadingFile(Boolean(attached));
    setSending(true);
    setSent(0);
    try {
      let res: any;
      if (attached) {
        try {
          res = await apiUpload<any>("/desk/chat/file", attached, setSent, { note: text });
        } catch (err: any) {
          if (!/not found/i.test(err.message || "")) throw err;
          const saved = await apiUpload<any>("/setup/import/company?commit=true", attached, setSent);
          res = {
            synced: true,
            upload: saved.upload,
            kinds: saved.kinds,
            reply: describeImport(attached.name, saved),
          };
          rememberUploadLocally(saved.upload || saved);
        }
      } else {
        try {
          res = await api<any>("/desk/chat", { method: "POST", body: JSON.stringify({ message: text, history }) });
        } catch (err: any) {
          if (!/not found/i.test(err.message || "")) throw err;
          res = {
            reply: answerFromScreen(text, {
              openCases,
              waitingYou,
              pastSla,
              employees,
              locations,
              percent: upload.percent,
              saved: upload.saved,
              total: upload.total,
              last: lastImport,
            }),
          };
        }
      }
      setMessages((prev) => [...prev, { role: "desk", text: res.reply || "Done." }]);
      if (res.reply) setLastImport(res.reply);
      if (res.upload) rememberUploadLocally(res.upload);
      if (res.synced) load();
    } catch (err: any) {
      setMessages((prev) => [...prev, { role: "desk", text: err.message || "That did not go through." }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <AppShell
      title="Desk Chat"
      subtitle="Ask about company records or drop an Excel workbook to import."
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Desk Chat" }]}
      actions={
        <button className="btn secondary" onClick={load} disabled={busy}>
          {busy ? "Refreshing…" : "Refresh"}
        </button>
      }
    >
      {error && (
        <div className="panel" style={{ marginBottom: "1rem", borderColor: "#f0b4ae" }}>
          <strong style={{ color: "var(--danger)" }}>{error}</strong>
        </div>
      )}

      <div className="metric-bar" style={{ marginBottom: "1rem" }}>
        <Link href="/outcomes" className="metric">
          <span>Open</span>
          <strong>{openCases}</strong>
          <em>Still with the teams</em>
        </Link>
        <Link href="/reviews" className="metric">
          <span>Your decision</span>
          <strong>{waitingYou}</strong>
          <em>Approvals and confirmations</em>
        </Link>
        <Link href="/outcomes" className={`metric ${pastSla > 0 ? "hot" : ""}`}>
          <span>Past due</span>
          <strong>{pastSla}</strong>
          <em>Missed the agreed time</em>
        </Link>
        <Link href="/setup" className="metric">
          <span>Excel</span>
          <strong>{upload.percent}%</strong>
          <em>
            {employees} people · {locations} offices
          </em>
        </Link>
      </div>

      <section
        className="chat-app"
        onDragOver={(ev) => ev.preventDefault()}
        onDrop={(ev) => {
          ev.preventDefault();
          const next = ev.dataTransfer.files?.[0];
          if (next) setFile(next);
        }}
      >
        <div className="chat-log" ref={logRef}>
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              {m.text}
            </div>
          ))}
          {sending && (
            <div className="bubble desk">{readingFile ? `Reading the file… ${sent}%` : "Checking the records…"}</div>
          )}
        </div>
        <form className="composer" onSubmit={onSend}>
          {file && (
            <div className="file-chip">
              {file.name}
              <button type="button" className="btn ghost" onClick={() => setFile(null)}>
                Remove
              </button>
            </div>
          )}
          <div className="composer-row">
            <label className="btn secondary" style={{ cursor: "pointer" }}>
              Excel
              <input
                type="file"
                accept=".xlsx,.xlsm,.csv"
                hidden
                onChange={(ev) => setFile(ev.target.files?.[0] || null)}
              />
            </label>
            <textarea
              value={draft}
              placeholder="Ask a question, or attach an Excel file"
              rows={1}
              onChange={(ev) => setDraft(ev.target.value)}
              onKeyDown={(ev) => {
                if (ev.key === "Enter" && !ev.shiftKey) {
                  ev.preventDefault();
                  onSend();
                }
              }}
            />
            <button className="btn accent" type="submit" disabled={sending || (!draft.trim() && !file)}>
              Send
            </button>
          </div>
        </form>
      </section>
    </AppShell>
  );
}
