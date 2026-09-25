import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Sidebar } from "../components/Sidebar";
import { MaterialsPanel } from "../components/MaterialsPanel";
import { StatisticsPanel } from "../components/StatisticsPanel";
import { CrmBoard } from "./Board";
import { useAuth, describeError } from "../auth/AuthContext";
import { api, type ReportingSettings, type ReportingSettingsUpdate } from "../api/client";

const BOARD_VIEWS = ["board", "statistics", "materials"] as const;
type BoardTab = (typeof BOARD_VIEWS)[number];

function isBoardTab(value: string | null): value is BoardTab {
  return value !== null && (BOARD_VIEWS as readonly string[]).includes(value);
}

export default function Dashboard() {
  const { token, businessId } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const pageTab: BoardTab = isBoardTab(searchParams.get("view")) ? searchParams.get("view") as BoardTab : "board";
  const [reporting, setReporting] = useState<ReportingSettings | null>(null);
  const [reportingSaving, setReportingSaving] = useState(false);
  const [reportingError, setReportingError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !businessId) return;
    api.getReportingSettings(token, businessId).then(setReporting).catch((err) => setReportingError(describeError(err)));
  }, [token, businessId]);

  const setPageTab = (next: BoardTab) => {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set("view", next);
      return params;
    }, { replace: true });
  };

  const updateReporting = async (update: ReportingSettingsUpdate) => {
    if (!token || !businessId) return false;
    setReportingSaving(true);
    setReportingError(null);
    try {
      setReporting(await api.updateReportingSettings(token, businessId, update));
      return true;
    } catch (err) {
      setReportingError(describeError(err));
      return false;
    } finally {
      setReportingSaving(false);
    }
  };

  return (
    <div className="ev-page min-h-screen w-full flex">
      <Sidebar />
      <main className="flex-1 min-w-0 flex flex-col pt-14 md:pt-0">
        <header className="flex flex-wrap items-center justify-between gap-3 px-6 md:px-8 py-4 border-b border-line">
          <div>
            <h1 className="text-xl font-semibold">CRM</h1>
            <p className="text-sm text-mute mt-0.5">Watch the path. The engine writes. You do not hop in to close.</p>
          </div>
          <div className="flex items-center gap-2">
            {([
              ["board", "Board"],
              ["statistics", "Statistics"],
              ["materials", "Advertising materials"],
            ] as const).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setPageTab(key)}
                className="px-3 py-1.5 rounded-full text-xs font-medium"
                style={{ backgroundColor: pageTab === key ? "#C6FF00" : "transparent", color: pageTab === key ? "#0B0B0D" : "#6B6459" }}
              >
                {label}
              </button>
            ))}
          </div>
        </header>

        {pageTab === "statistics" && token && businessId && (
          <div className="p-6 md:p-8">
            <StatisticsPanel
              token={token}
              businessId={businessId}
              reporting={reporting}
              reportingSaving={reportingSaving}
              reportingError={reportingError}
              onUpdateReporting={updateReporting}
            />
          </div>
        )}

        {pageTab === "materials" && token && businessId && (
          <div className="p-6 md:p-8 max-w-3xl">
            <MaterialsPanel token={token} businessId={businessId} />
          </div>
        )}

        {pageTab === "board" && <CrmBoard />}
      </main>
    </div>
  );
}
