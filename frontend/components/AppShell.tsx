"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken, getToken, api } from "@/lib/api";
import { useEffect, useState } from "react";

const PRIMARY = [
  { href: "/", label: "Overview" },
  { href: "/outcomes", label: "Requests" },
  { href: "/reviews", label: "Needs a decision" },
  { href: "/setup", label: "Company data" },
  { href: "/email", label: "Mail inbox" },
];

const MORE = [
  { href: "/tasks", label: "Team tasks" },
  { href: "/resources", label: "Rooms & assets" },
  { href: "/config", label: "Preferences" },
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
  const [showMore, setShowMore] = useState(false);

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
      <div className="boot-screen">
        <div className="boot-mark">Desk</div>
        <p className="muted">Opening your workplace console…</p>
      </div>
    );
  }

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  const mailReady = Boolean(mailin?.can_send_replies || mailin?.smtp_configured);

  return (
    <div className="shell">
      <div className={`nav-backdrop ${open ? "show" : ""}`} onClick={() => setOpen(false)} />
      <aside className={`nav ${open ? "open" : ""}`}>
        <div className="brand-block">
          <div className="brand-mark">Desk</div>
          <p className="brand-sub">Workplace admin</p>
        </div>

        <nav className="nav-primary" aria-label="Main">
          {PRIMARY.map((l) => (
            <Link key={l.href} href={l.href} className={isActive(l.href) ? "active" : ""}>
              {l.label}
            </Link>
          ))}
        </nav>

        <button type="button" className="nav-more-toggle" onClick={() => setShowMore((v) => !v)}>
          {showMore ? "Hide more" : "More"}
        </button>
        {showMore && (
          <nav className="nav-more" aria-label="More">
            {MORE.map((l) => (
              <Link key={l.href} href={l.href} className={isActive(l.href) ? "active" : ""}>
                {l.label}
              </Link>
            ))}
          </nav>
        )}

        <div className="nav-footer">
          <div className="nav-status">
            <div className="row" style={{ gap: "0.45rem" }}>
              <span className={`live-dot ${mailReady ? "" : "off"}`} />
              <strong>Employee mail</strong>
            </div>
            <p className="muted">
              {mailin?.address || "Inbox address not set yet"}
              <br />
              {mailReady ? "Can send replies" : "Receiving only — replies not configured"}
            </p>
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
            <button type="button" className="nav-toggle" onClick={() => setOpen(true)}>
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
