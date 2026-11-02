"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@prototype.local");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(email, password);
      router.replace("/");
    } catch (err: any) {
      setError(err.message || "Could not sign in");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap as-login">
      <section className="login-hero as-login-hero">
        <div className="as-logo" style={{ marginBottom: "1.5rem" }}>
          <span className="as-mark">A</span>
          <div>
            <div className="brand-mark" style={{ color: "#fff", fontSize: "1.35rem" }}>
              AdminServices
            </div>
            <p className="brand-sub" style={{ color: "rgba(255,255,255,0.65)" }}>
              Workplace admin
            </p>
          </div>
        </div>
        <p className="eyebrow" style={{ color: "#93c5fd" }}>
          Corporate console
        </p>
        <h1 style={{ color: "#fff" }}>Run vendors, facilities, and master data in one place</h1>
        <p style={{ color: "rgba(255,255,255,0.75)" }}>
          Onboard vendors, track employee requests, import company data, and keep every office moving —
          without living in the shared inbox.
        </p>
      </section>
      <section className="login-side">
        <form className="login-card" onSubmit={onSubmit}>
          <h2>Sign in</h2>
          <p className="muted" style={{ marginBottom: "1.25rem" }}>
            For your company&apos;s workplace admin team
          </p>
          <div className="field">
            <label>Work email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          {error && (
            <p className="badge danger" style={{ marginBottom: "0.75rem" }}>
              {error}
            </p>
          )}
          <button className="btn accent" style={{ width: "100%" }} disabled={loading}>
            {loading ? "Signing in…" : "Enter AdminServices"}
          </button>
        </form>
      </section>
    </div>
  );
}
