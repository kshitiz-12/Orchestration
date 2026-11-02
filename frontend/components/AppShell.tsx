"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken, getToken, api } from "@/lib/api";
import { FormEvent, useEffect, useState } from "react";

type NavLeaf = { href: string; label: string };
type NavGroup = {
  id: string;
  label: string;
  icon: string;
  href?: string;
  children?: NavLeaf[];
  match?: (path: string) => boolean;
};

const NAV: NavGroup[] = [
  { id: "dash", label: "Dashboard", icon: "⌂", href: "/" },
  {
    id: "vendors",
    label: "Vendor Management",
    icon: "▦",
    match: (p) => p.startsWith("/vendors") || p.startsWith("/reviews"),
    children: [
      { href: "/vendors", label: "Vendors" },
      { href: "/vendors/onboarding", label: "Onboarding" },
      { href: "/reviews", label: "Approvals" },
      { href: "/vendors?tab=contracts", label: "Contracts" },
      { href: "/vendors?tab=performance", label: "Performance" },
    ],
  },
  { id: "facilities", label: "Facilities Management", icon: "▣", href: "/outcomes" },
  { id: "amc", label: "AMC Management", icon: "⟳", href: "/tasks?type=AMC" },
  { id: "procurement", label: "Procurement", icon: "✉", href: "/email" },
  { id: "assets", label: "Assets", icon: "▢", href: "/resources" },
  { id: "workorders", label: "Work Orders", icon: "☰", href: "/tasks" },
  { id: "invoices", label: "Invoices & Payments", icon: "₹", href: "/invoices" },
  { id: "reports", label: "Reports", icon: "▤", href: "/learning" },
  { id: "master", label: "Master Data", icon: "⚙", href: "/setup" },
  { id: "settings", label: "Settings", icon: "◎", href: "/config" },
];

function isLeafActive(pathname: string, href: string) {
  const base = href.split("?")[0];
  if (base === "/") return pathname === "/";
  if (base === "/vendors") return pathname === "/vendors";
  if (base === "/vendors/onboarding") return pathname.startsWith("/vendors/onboarding");
  return pathname === base || pathname.startsWith(`${base}/`);
}

function NavIcon({ icon }: { icon: string }) {
  return <span className="nav-ico" aria-hidden>{icon}</span>;
}

export function AppShell({
  children,
  title,
  subtitle,
  breadcrumbs,
  actions,
  hideHeader,
}: {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  breadcrumbs?: { label: string; href?: string }[];
  actions?: React.ReactNode;
  hideHeader?: boolean;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [open, setOpen] = useState(false);
  const [mailin, setMailin] = useState<any>(null);
  const [q, setQ] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    if (pathname === "/login") {
      setAuthed(true);
      return;
    }
    if (!getToken()) {
      setAuthed(false);
      router.replace("/login");
    } else {
      setAuthed(true);
    }
  }, [mounted, pathname, router]);

  useEffect(() => {
    if (!mounted || !authed || pathname === "/login") return;
    api("/webhooks/cloudmailin")
      .then(setMailin)
      .catch(() => setMailin(null));
  }, [mounted, authed, pathname]);

  useEffect(() => {
    setOpen(false);
    setExpanded((e) => ({
      ...e,
      vendors: pathname.startsWith("/vendors") || pathname.startsWith("/reviews"),
    }));
  }, [pathname]);

  if (pathname === "/login") return <>{children}</>;
  if (!mounted || !authed) {
    return (
      <div className="boot-screen" suppressHydrationWarning>
        <div className="boot-mark">AdminServices</div>
        <p className="muted">Opening your workplace console…</p>
      </div>
    );
  }

  function onSearch(e: FormEvent) {
    e.preventDefault();
    const term = q.trim();
    if (!term) return;
    if (/vendor|onboard|gst|pan/i.test(term)) {
      router.push(`/vendors?q=${encodeURIComponent(term)}`);
      return;
    }
    router.push(`/outcomes?q=${encodeURIComponent(term)}`);
  }

  const mailReady = Boolean(mailin?.can_send_replies || mailin?.smtp_configured);

  return (
    <div className="shell admin-services">
      <div className={`nav-backdrop ${open ? "show" : ""}`} onClick={() => setOpen(false)} />
      <aside className={`nav ${open ? "open" : ""}`}>
        <div className="brand-block as-brand">
          <div className="as-logo">
            <span className="as-mark">A</span>
            <div>
              <div className="brand-mark">AdminServices</div>
              <p className="brand-sub">Workplace admin</p>
            </div>
          </div>
        </div>

        <nav className="nav-primary" aria-label="Main">
          {NAV.map((item) => {
            if (item.children?.length) {
              const openGroup = expanded[item.id] ?? false;
              const groupActive = item.match?.(pathname) ?? false;
              return (
                <div key={item.id} className={`nav-accordion ${openGroup ? "open" : ""} ${groupActive ? "active" : ""}`}>
                  <button
                    type="button"
                    className="nav-accordion-btn"
                    onClick={() => setExpanded((e) => ({ ...e, [item.id]: !openGroup }))}
                  >
                    <NavIcon icon={item.icon} />
                    <span>{item.label}</span>
                    <em className="nav-chevron">{openGroup ? "▾" : "▸"}</em>
                  </button>
                  {openGroup ? (
                    <div className="nav-group">
                      {item.children.map((leaf) => (
                        <Link
                          key={leaf.href}
                          href={leaf.href}
                          className={isLeafActive(pathname, leaf.href) ? "active" : ""}
                        >
                          {leaf.label}
                        </Link>
                      ))}
                    </div>
                  ) : null}
                </div>
              );
            }

            const href = item.href || "/";
            const active = isLeafActive(pathname, href);
            return (
              <Link key={item.id} href={href} className={`nav-main-link ${active ? "active" : ""}`}>
                <NavIcon icon={item.icon} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

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
          <Link href="/chat" className="nav-desk-link">
            Desk Chat
          </Link>
          <Link href="/failures" className="nav-desk-link">
            Failures
          </Link>
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
        <div className="as-topbar">
          <button type="button" className="nav-toggle" onClick={() => setOpen(true)}>
            Menu
          </button>
          <form className="as-search-form" onSubmit={onSearch}>
            <input
              className="as-search-input"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search vendors, services, documents…"
            />
          </form>
          <div className="as-top-right">
            <Link href="/reviews" className="as-bell" title="Approvals">
              🔔<span className="dot" />
            </Link>
            <Link href="/config" className="as-help" title="Help & settings">
              ?
            </Link>
            <div className="as-user">
              <span className="as-avatar">AS</span>
              <div>
                <strong>Admin User</strong>
                <em>Corporate Admin</em>
              </div>
            </div>
          </div>
        </div>

        {!hideHeader && (title || subtitle || actions || breadcrumbs) ? (
          <div className="topbar as-page-head">
            <div>
              {breadcrumbs?.length ? (
                <p className="as-crumbs">
                  {breadcrumbs.map((c, i) => (
                    <span key={`${c.label}-${i}`}>
                      {i > 0 ? <span className="sep">›</span> : null}
                      {c.href ? <Link href={c.href}>{c.label}</Link> : c.label}
                    </span>
                  ))}
                </p>
              ) : null}
              {title ? <h1 className="page-title">{title}</h1> : null}
              {subtitle ? <p className="page-sub">{subtitle}</p> : null}
            </div>
            {actions ? <div className="row">{actions}</div> : null}
          </div>
        ) : null}
        <div className="main-content">{children}</div>
      </main>
    </div>
  );
}
