export type OnboardingStep = {
  id: number;
  key: string;
  title: string;
  subtitle: string;
};

export type OnboardingDraft = {
  current_step: number;
  basic: Record<string, any>;
  business: Record<string, any>;
  compliance: Record<string, any>;
  pricing: Record<string, any>;
  bank: Record<string, any>;
  review: Record<string, any>;
};

export type OnboardingPayload = {
  vendor_id: string;
  name: string;
  status: string;
  contact_email?: string;
  registration_url?: string | null;
  expires_at?: string | null;
  steps: OnboardingStep[];
  draft: OnboardingDraft;
  readiness: {
    percent: number;
    ready: boolean;
    checks: { label: string; ok: boolean }[];
  };
  mode: "company" | "vendor";
};

export const VENDOR_TYPES = [
  "Facilities Management",
  "AMC",
  "Supplies",
  "Repair & Maintenance",
  "Security Services",
  "Housekeeping",
  "IT/AV Services",
  "Pest Control",
  "Landscaping/Horticulture",
  "Other",
];

export const SERVICE_CATEGORIES = [
  { id: "hvac", label: "HVAC / Air Conditioning", icon: "❄" },
  { id: "electrical", label: "Electrical & DG", icon: "⚡" },
  { id: "fire", label: "Fire & Life Safety", icon: "🔥" },
  { id: "civil", label: "Civil & Plumbing", icon: "🔧" },
  { id: "housekeeping", label: "Housekeeping", icon: "🧹" },
  { id: "security", label: "Security Services", icon: "🛡" },
  { id: "pest", label: "Pest Control", icon: "🐛" },
  { id: "landscape", label: "Landscaping", icon: "🌿" },
  { id: "it", label: "IT / AV", icon: "💻" },
  { id: "supplies", label: "Office Supplies", icon: "📦" },
];

export const SERVICE_OFFER_TAGS = [
  "Installation",
  "Repair",
  "Preventive Maintenance",
  "Breakdown Support",
  "AMC",
  "Retrofit",
];

export const EQUIPMENT_TAGS = ["Daikin", "Carrier", "Voltas", "Blue Star", "LG", "Mitsubishi"];

export const CITY_OPTIONS = [
  "Delhi",
  "Gurgaon",
  "Noida",
  "Mumbai",
  "Bengaluru",
  "Hyderabad",
  "Pune",
  "Chennai",
  "Kolkata",
  "Ahmedabad",
];

export const COVERAGE_TYPES = ["Single city", "Multiple cities", "Multiple states", "Pan India"];

export const INVOICE_INFO_TAGS = [
  "PO/WO Number",
  "Branch Name & Address",
  "GST Details",
  "HSN/SAC Code",
  "Bank Details",
];

export const DEFAULT_DOCUMENTS = [
  { type: "PAN Card", applicable: "Yes", details: "", file_name: "", expiry: "", status: "Pending" },
  { type: "GST Registration", applicable: "Yes", details: "", file_name: "", expiry: "", status: "Pending" },
  { type: "Certificate of Incorporation", applicable: "Yes", details: "", file_name: "", expiry: "", status: "Pending" },
  { type: "Trade License", applicable: "Conditional", details: "", file_name: "", expiry: "", status: "Pending" },
  { type: "Cancelled Cheque", applicable: "Yes", details: "", file_name: "", expiry: "", status: "Pending" },
];

export const PRICING_TABS = [
  { key: "amc", label: "AMC Contracts" },
  { key: "labour", label: "Labour & Service Rates" },
  { key: "spares", label: "Spare Parts & Materials" },
  { key: "manpower", label: "Manpower / Monthly Rates" },
  { key: "catalogue", label: "Supplier Catalogue" },
  { key: "terms", label: "Commercial Terms" },
] as const;

export const APPROVAL_ROWS = [
  { team: "Facilities", status: "Pending" },
  { team: "Procurement", status: "Pending" },
  { team: "Finance", status: "Pending" },
  { team: "Legal / Compliance", status: "Not Required" },
  { team: "Authorized Approver", status: "Pending" },
];
