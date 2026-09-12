"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken, getToken, api } from "@/lib/api";
import { useEffect, useState } from "react";

const GROUPS = [
  {
    label: "Start here",
    links: [{ href: "/", label: "Home" }],
  },
  {
    label: "Daily work",
    links: [
      { href: "/reviews", label: "Needs your decision" },
      { href: "/outcomes", label: "All requests" },
      { href: "/tasks", label: "Team tasks" },
    ],
  },
  {
    label: "Email",
    links: [{ href: "/email", label: "Email intake" }],
  },
  {
    label: "More",
    links: [
      { href: "/resources", label: "Rooms & seats" },
      { href: "/invoices", label: "Invoices" },
      { href: "/failures", label: "Problems" },
      { href: "/config", label: "Settings" },
    ],
  },
];

export function AppShell({
  children,
  title,
  subtitle,
  actions,
}: {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [open, setOpen] = useState(false);
  const [mailin, setMailin] = useState<any>(null);

  useEffect(() => {
    if (!getToken() && pathname !== "/login") {
      router.replace("/login");
    } else {
      setReady(true);
    }
  }, [pathname, router]);

  useEffect(() => {
    if (!ready || pathname === "/login") return;
    api("/webhooks/cloudmailin")
      .then(setMailin)
      .catch(() => setMailin(null));
  }, [ready, pathname]);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  if (pathname === "/login") return <>{children}</>;
  if (!ready) {
    return (
      <div className="login-wrap" style={{ gridTemplateColumns: "1fr" }}>
        <div className="empty">Loading console…</div>
      </div>
    );
  }

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <div className="shell">
      <div className={`nav-backdrop ${open ? "show" : ""}`} onClick={() => setOpen(false)} />
      <aside className={`nav ${open ? "open" : ""}`}>
        <div className="brand-block">
          <h1 className="brand">
            Outcome <span>Orchestrate</span>
          </h1>
          <div className="brand-sub">Email requests → clear next steps</div>
        </div>

        {GROUPS.map((g) => (
          <div className="nav-group" key={g.label}>
            <div className="nav-group-label">{g.label}</div>
            {g.links.map((l) => (
              <Link key={l.href} href={l.href} className={isActive(l.href) ? "active" : ""}>
                {l.label}
              </Link>
            ))}
          </div>
        ))}

        <div className="nav-footer">
          <div className="panel" style={{ padding: "0.75rem 0.85rem", marginBottom: "0.75rem" }}>
            <div className="row" style={{ gap: "0.45rem" }}>
              <span className={`live-dot ${mailin?.smtp_configured ? "" : "off"}`} />
              <strong style={{ fontSize: "0.82rem" }}>Email</strong>
            </div>
            <div className="muted" style={{ fontSize: "0.75rem", marginTop: "0.35rem" }}>
              {mailin?.address || "Intake address not set"}
              <br />
              {mailin?.can_send_replies || mailin?.smtp_configured
                ? "Can send replies"
                : "Receiving only"}
            </div>
          </div>
          <button
            className="btn secondary"
            style={{ width: "100%" }}
            onClick={() => {
              clearToken();
              router.push("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div>
            <button type="button" className="nav-toggle" onClick={() => setOpen(true)} style={{ marginBottom: "0.75rem" }}>
              Menu
            </button>
            {title ? <h1 className="page-title">{title}</h1> : null}
            {subtitle ? <p className="page-sub">{subtitle}</p> : null}
          </div>
          {actions ? <div className="row">{actions}</div> : null}
        </div>
        <div className="main-content">{children}</div>
      </main>
    </div>
  );
}
