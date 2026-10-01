/** Plain-language labels for non-technical operators */

export function friendlyType(code?: string) {
  const map: Record<string, string> = {
    MEETING_ROOM: "Meeting room",
    ONBOARDING: "New joiner",
    PARKING_CONFLICT: "Parking",
    FURNITURE_ISSUE: "Furniture",
    VENDOR_ESCALATION: "Vendor",
    INVOICE: "Invoice",
    GENERAL: "General request",
    SERVICE_REQUEST: "Service request",
  };
  return map[code || ""] || (code || "Request").replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());
}

/** Request type for any case: the backend's type_label, then the desk category label, then the template. */
export function requestType(o: any): string {
  if (!o) return "Request";
  return o.type_label || o.facts?.category_label || friendlyType(o.template_code);
}

export function friendlyPriority(p?: string) {
  const map: Record<string, string> = { URGENT: "Urgent", HIGH: "High", MEDIUM: "Normal", LOW: "Low" };
  return map[p || ""] || "Normal";
}

export function priorityTone(p?: string): "danger" | "warn" | "" {
  if (p === "URGENT") return "danger";
  if (p === "HIGH") return "warn";
  return "";
}

export function friendlyWaitingOn(w?: string) {
  const map: Record<string, string> = {
    requester: "Requester",
    approver: "Approver",
    team: "Team",
    admin: "You (admin)",
    nobody: "—",
  };
  return map[w || ""] || "—";
}

export function friendlyStatus(status?: string) {
  const map: Record<string, string> = {
    ACTIVE: "In progress",
    AT_RISK: "At risk",
    RESOLVED: "Resolved",
    REOPENED: "Reopened",
    CLOSED: "Done",
    CANCELLED: "Cancelled",
    DRAFT: "Draft",
    PENDING: "Waiting",
    ASSIGNED: "Assigned",
    ACCEPTED: "Accepted",
    IN_PROGRESS: "Working",
    ON_HOLD: "On hold",
    COMPLETED_PENDING_EVIDENCE: "Needs proof",
    VERIFIED: "Verified",
    ACTION_PENDING: "Action needed",
    INFORMATION_REQUIRED: "Need more info",
    BLOCKED: "Blocked",
    FAILED: "Failed",
  };
  return map[status || ""] || (status || "—").replaceAll("_", " ");
}

export function friendlyAudit(action?: string) {
  const map: Record<string, string> = {
    OUTCOME_CREATED: "Request created",
    OUTCOME_UPDATED: "Request updated",
    TASK_CREATED: "Task created",
    TASK_COMPLETED: "Task completed",
    COMMUNICATION_SENT: "Email sent",
    CLARIFICATION_SENT: "Asked for more details",
    AI_EXTRACTION_COMPLETED: "System read the email",
    AI_REVIEW_REQUIRED: "Sent for human decision",
    HUMAN_OVERRIDE: "Human decision recorded",
    INFORMATION_MERGED: "Details updated from reply",
    EMAIL_RECEIVED: "Email received",
    EMAIL_DEDUPLICATED: "Duplicate email ignored",
    COMMUNICATION_SUPPRESSED: "Outbound email suppressed",
    OUTCOME_REOPENED: "Request reopened",
    OUTCOME_CLOSED: "Request closed",
    OUTCOME_VERIFIED: "Request verified",
  };
  return map[action || ""] || (action || "—").replaceAll("_", " ");
}
