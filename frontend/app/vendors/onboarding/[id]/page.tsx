"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { VendorOnboardingWizard } from "@/components/vendor-onboarding/Wizard";
import { OnboardingDraft, OnboardingPayload } from "@/components/vendor-onboarding/types";
import { api } from "@/lib/api";

export default function CompanyVendorOnboardingPage() {
  const params = useParams();
  const id = String(params?.id || "");
  const [payload, setPayload] = useState<OnboardingPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    api<OnboardingPayload>(`/vendors/${id}/onboarding`)
      .then(setPayload)
      .catch((e) => setError(e.message || "Could not load onboarding"));
  }, [id]);

  if (error) {
    return (
      <AppShell title="Vendor Onboarding">
        <p className="muted">{error}</p>
      </AppShell>
    );
  }
  if (!payload) {
    return (
      <AppShell title="Vendor Onboarding">
        <p className="muted">Loading onboarding…</p>
      </AppShell>
    );
  }

  return (
    <AppShell hideHeader>
      <VendorOnboardingWizard
        key={payload.vendor_id}
        initial={payload}
        mode="company"
        onSave={async (draft: OnboardingDraft) =>
          api<OnboardingPayload>(`/vendors/${id}/onboarding`, {
            method: "PUT",
            body: JSON.stringify({ draft }),
          })
        }
        onSubmit={async () =>
          api(`/vendors/${id}/onboarding/submit`, {
            method: "POST",
            body: "{}",
          })
        }
      />
    </AppShell>
  );
}
