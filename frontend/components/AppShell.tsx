"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken, getToken } from "@/lib/api";
import { useEffect, useState } from "react";

const LINKS = [
  { href: "/", label: "Operations" },
  { href: "/outcomes", label: "Outcomes" },
  { href: "/reviews", label: "Human Review" },
  { href: "/tasks", label: "Task Workspace" },
  { href: "/resources", label: "Resources" },
  { href: "/invoices", label: "Invoice Workbench" },
  { href: "/failures", label: "Failure Console" },
  { href: "/config", label: "Configuration" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken() && pathname !== "/login") {
      router.replace("/login");
    } else {
      setReady(true);
    }
  }, [pathname, router]);

  if (pathname === "/login") return <>{children}</>;
  if (!ready) return null;

  return (
    <div className="shell">
      <aside className="nav">
        <h1 className="brand">Outcome Orchestration</h1>
        <div className="brand-sub">Prototype operations console</div>
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className={pathname === l.href ? "active" : ""}>
            {l.label}
          </Link>
        ))}
        <button
          className="btn secondary"
          style={{ marginTop: "1.5rem", width: "100%" }}
          onClick={() => {
            clearToken();
            router.push("/login");
          }}
        >
          Sign out
        </button>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
