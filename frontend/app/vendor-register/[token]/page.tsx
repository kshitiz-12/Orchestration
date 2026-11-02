"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { VendorOnboardingWizard } from "@/components/vendor-onboarding/Wizard";
import { OnboardingDraft, OnboardingPayload } from "@/components/vendor-onboarding/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

async function publicApi<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.message || "Request failed");
  return data as T;
}

function VendorPortalChrome({ children }: { children: React.ReactNode }) {
  return (
    <div className="vo-portal">
      <aside className="vo-portal-nav">
        <div className="vo-portal-brand">
          <span className="vo-portal-mark">A</span>
          AdminServices
        </div>
        <span className="nav-item">Dashboard</span>
        <span className="nav-item">Vendor Management</span>
        <span className="nav-item sub active">Onboarding</span>
        <span className="nav-item">Facilities Management</span>
        <span className="nav-item">AMC Management</span>
        <span className="nav-item">Procurement</span>
        <span className="nav-item">Invoices & Payments</span>
        <span className="nav-item">Reports</span>
        <span className="nav-item">Settings</span>
      </aside>
      <div className="vo-portal-main">
        <header className="vo-portal-top">
          <div className="vo-portal-search">Search vendors, contracts, services…</div>
          <div className="vo-portal-user">
            <span className="vo-portal-avatar">V</span>
            <div>
              <strong>Vendor User</strong>
              <em>Self-service onboarding</em>
            </div>
          </div>
        </header>
        <div className="vo-portal-body">{children}</div>
      </div>
    </div>
  );
}

export default function VendorRegisterPage() {
  const params = useParams();
  const token = String(params?.token || "");
  const [payload, setPayload] = useState<OnboardingPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    publicApi<OnboardingPayload>(`/public/vendors/register/${token}`)
      .then(setPayload)
      .catch((e) => setError(e.message || "Could not open onboarding link"));
  }, [token]);

  if (error) {
    return (
      <VendorPortalChrome>
        <div className="vo-done">
          <h1>Link unavailable</h1>
          <p>{error}</p>
        </div>
      </VendorPortalChrome>
    );
  }

  if (!payload) {
    return (
      <VendorPortalChrome>
        <div className="vo-done">
          <h1>Opening onboarding…</h1>
          <p>Loading your registration form.</p>
        </div>
      </VendorPortalChrome>
    );
  }

  return (
    <VendorPortalChrome>
      <VendorOnboardingWizard
        key={payload.vendor_id}
        initial={payload}
        mode="vendor"
        onSave={async (draft: OnboardingDraft) =>
          publicApi<OnboardingPayload>(`/public/vendors/register/${token}`, {
            method: "PUT",
            body: JSON.stringify({ draft }),
          })
        }
        onSubmit={async () =>
          publicApi(`/public/vendors/register/${token}/submit`, {
            method: "POST",
            body: "{}",
          })
        }
      />
    </VendorPortalChrome>
  );
}
