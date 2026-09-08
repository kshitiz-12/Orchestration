"use client";

import { AppShell } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEffect, useState } from "react";

export default function InvoicesPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  function load() {
    api("/invoices").then(setRows).catch((e) => setMsg(e.message));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <AppShell>
      <h1 className="page-title">Invoice Workbench</h1>
      <p className="page-sub">Three-way match · exceptions · human approval · mock ERP handoff (never auto-pay).</p>
      {msg && <p className="muted">{msg}</p>}
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Invoice</th>
              <th>Vendor</th>
              <th>PO</th>
              <th>Receipt</th>
              <th>Match</th>
              <th>ERP</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.invoice.invoice_id}>
                <td>
                  {row.invoice.invoice_number}
                  <div className="muted">
                    {row.invoice.amount} {row.invoice.currency}
                  </div>
                </td>
                <td>{row.vendor?.name || "—"}</td>
                <td>{row.po?.po_number || "—"}</td>
                <td>{row.receipt ? `${row.receipt.quantity_received} received` : "—"}</td>
                <td>
                  <span className="badge">{row.invoice.match_status}</span>
                  {row.invoice.bank_details_changed && <span className="badge danger"> bank change</span>}
                </td>
                <td>{row.invoice.erp_handoff_status}</td>
                <td>
                  <button
                    className="btn secondary"
                    onClick={async () => {
                      const res = await api(`/invoices/${row.invoice.invoice_id}/erp-handoff`, { method: "POST" });
                      setMsg(JSON.stringify(res.handoff));
                      load();
                    }}
                  >
                    ERP handoff
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
