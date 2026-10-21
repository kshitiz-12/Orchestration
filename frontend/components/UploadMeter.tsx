const LOCAL_KEY = "desk_excel_upload";

type UploadSource = {
  total?: number;
  saved?: number;
  new?: number;
  updated?: number;
  problems?: number;
  errors?: unknown[];
  percent?: number;
  filename?: string;
  upload?: UploadSource;
};

export function uploadFigures(source: UploadSource | null | undefined) {
  const row = source?.upload && typeof source.upload === "object" ? source.upload : source;
  const total = Number(row?.total || 0);
  const saved =
    row?.saved != null ? Number(row.saved) : Number(row?.new || 0) + Number(row?.updated || 0);
  const problems =
    row?.problems != null ? Number(row.problems) : Array.isArray(row?.errors) ? row.errors.length : 0;
  const percent = total > 0 ? Math.round((100 * saved) / total) : 0;
  return {
    total,
    saved,
    problems,
    percent: Math.min(100, Math.max(0, percent)),
    filename: (row?.filename || "").trim(),
  };
}

export function rememberUploadLocally(source: UploadSource | null | undefined) {
  const figures = uploadFigures(source);
  if (!figures.total || typeof window === "undefined") return;
  window.localStorage.setItem(LOCAL_KEY, JSON.stringify(figures));
}

export function readLocalUpload(): ReturnType<typeof uploadFigures> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LOCAL_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && Number(parsed.total) > 0 ? uploadFigures(parsed) : null;
  } catch {
    return null;
  }
}

export function UploadMeter({ source }: { source: UploadSource | null | undefined }) {
  const { total, saved, problems, percent, filename } = uploadFigures(source);
  const started = total > 0;
  return (
    <div className="upload-meter">
      <div className="upload-meter-top">
        <div>
          <div className="label">Excel uploaded</div>
          <div className="upload-count">
            {saved} <span>of {total}</span>
          </div>
        </div>
        <div className="upload-percent">{percent}%</div>
      </div>
      <div className="upload-track" aria-hidden="true">
        <div className="upload-fill" style={{ width: `${percent}%` }} />
      </div>
      <p className="muted">
        {started
          ? `${percent}% of the Excel is uploaded${filename ? ` (${filename})` : ""}.`
          : "0% — upload a company Excel file and this line fills as rows are saved."}
        {problems > 0 ? ` ${problems} row${problems === 1 ? "" : "s"} in the file ${problems === 1 ? "was" : "were"} not saved.` : ""}
      </p>
    </div>
  );
}
