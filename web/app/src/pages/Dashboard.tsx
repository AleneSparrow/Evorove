import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, Clock, Loader2, Phone, Mail } from "lucide-react";
import { Sidebar } from "../components/Sidebar";
import { MaterialsPanel } from "../components/MaterialsPanel";
import { StatisticsPanel } from "../components/StatisticsPanel";
import { useAuth, describeError } from "../auth/AuthContext";
import { api, type DashboardCaseSummary, type DashboardConversationDetail, type ReportingSettings, type ReportingSettingsUpdate } from "../api/client";
import {
  CRM_BOARD_TABS,
  CRM_TAB_META,
  mapCrmTab,
  type CrmTab,
} from "../lib/crmBoard";
import { formatRelativeTime } from "../components/Shared";

const BOARD_VIEWS = ["board", "statistics", "materials"] as const;
type BoardTab = (typeof BOARD_VIEWS)[number];

function isBoardTab(value: string | null): value is BoardTab {
  return value !== null && (BOARD_VIEWS as readonly string[]).includes(value);
}

export default function Dashboard() {
  const { token, businessId } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const pageTab: BoardTab = isBoardTab(searchParams.get("view")) ? searchParams.get("view") as BoardTab : "board";
  const requestedLead = searchParams.get("lead");
  const [cases, setCases] = useState<DashboardCaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [crmTab, setCrmTab] = useState<CrmTab>("cold");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [thread, setThread] = useState<DashboardConversationDetail | null>(null);
  const [threadMissing, setThreadMissing] = useState(false);
  const [threadLoading, setThreadLoading] = useState(false);
  const [reporting, setReporting] = useState<ReportingSettings | null>(null);
  const [reportingSaving, setReportingSaving] = useState(false);
  const [reportingError, setReportingError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!token || !businessId) return;
    api
      .listCases(token, businessId, { ignoreBaseline: true })
      .then((res) => {
        if (cancelled) return;
        setCases(res.cases);
        const fromUrl = requestedLead
          ? res.cases.find((item) => item.case_id === requestedLead)
          : undefined;
        const pick = fromUrl ?? res.cases[0];
        if (pick) {
          setSelectedId(pick.case_id);
          setCrmTab(mapCrmTab(pick.current_state));
        }
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [token, businessId, requestedLead]);

  useEffect(() => {
    if (!token || !businessId) return;
    api.getReportingSettings(token, businessId).then(setReporting).catch((err) => setReportingError(describeError(err)));
  }, [token, businessId]);

  const setPageTab = (next: BoardTab) => {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set("view", next);
      if (selectedId) params.set("lead", selectedId);
      return params;
    }, { replace: true });
  };

  const openLead = (caseId: string, tab: CrmTab) => {
    setSelectedId(caseId);
    setCrmTab(tab);
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set("view", "board");
      params.set("lead", caseId);
      return params;
    }, { replace: true });
  };

  const decorated = useMemo(
    () => (cases ?? []).map((item) => ({ ...item, crmTab: mapCrmTab(item.current_state) })),
    [cases],
  );

  const counts = useMemo(() => {
    const next: Record<CrmTab, number> = { cold: 0, in_progress: 0, offer_made: 0, done: 0, lost: 0 };
    decorated.forEach((item) => {
      next[item.crmTab] += 1;
    });
    return next;
  }, [decorated]);

  const filtered = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return decorated.filter((item) => {
      if (item.crmTab !== crmTab) return false;
      if (!query) return true;
      return [item.lead.name, item.lead.phone, item.lead.email, item.category, item.case_id, item.lead.region]
        .some((value) => value?.toLowerCase().includes(query));
    });
  }, [decorated, crmTab, searchQuery]);

  const selected = useMemo(
    () => decorated.find((item) => item.case_id === selectedId) ?? null,
    [decorated, selectedId],
  );

  useEffect(() => {
    let cancelled = false;
    if (!token || !businessId || !selectedId) {
      setThread(null);
      return;
    }
    setThreadLoading(true);
    setThreadMissing(false);
    api
      .listConversations(token, businessId)
      .then(async (res) => {
        const match = res.conversations.find((item) => item.case_id === selectedId);
        if (!match) {
          if (!cancelled) {
            setThread(null);
            setThreadMissing(true);
          }
          return;
        }
        const detail = await api.getConversation(token, businessId, match.conversation_id);
        if (!cancelled) {
          setThread(detail);
          setThreadMissing(false);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err));
      })
      .finally(() => {
        if (!cancelled) setThreadLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, businessId, selectedId]);

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

        {pageTab === "board" && (
          <div className="p-6 md:p-8 flex flex-col gap-6">
            {error && (
              <div className="px-4 py-3 rounded-lg text-sm" style={{ backgroundColor: "#FBEBE9", color: "#8A3225" }}>
                Couldn't load the board: {error}
              </div>
            )}
            {cases === null && !error ? (
              <div className="flex items-center gap-2 text-sm text-mute py-12 justify-center">
                <Loader2 size={16} className="animate-spin" /> Loading the board…
              </div>
            ) : (
              <div className="flex flex-col xl:flex-row gap-6 items-start">
                <div className="flex-1 min-w-0 bg-white rounded-2xl border border-line overflow-hidden w-full">
                  <div className="flex flex-wrap items-center gap-2 px-5 py-3 border-b border-line">
                    {CRM_BOARD_TABS.map((tab) => (
                      <button
                        key={tab}
                        type="button"
                        onClick={() => setCrmTab(tab)}
                        className="px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap"
                        style={{ backgroundColor: crmTab === tab ? "#FFE8E1" : "transparent", color: crmTab === tab ? "#FF5A36" : "#6B6459" }}
                      >
                        {CRM_TAB_META[tab].label} ({counts[tab]})
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => setCrmTab("lost")}
                      className="px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap"
                      style={{ backgroundColor: crmTab === "lost" ? "#F1F1EF" : "transparent", color: "#6B6459" }}
                    >
                      Lost ({counts.lost})
                    </button>
                    <div className="relative ml-auto">
                      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-clay" />
                      <input
                        aria-label="Search leads"
                        placeholder="Search leads…"
                        value={searchQuery}
                        onChange={(event) => setSearchQuery(event.target.value)}
                        className="pl-9 pr-3 py-2 rounded-lg bg-white border border-line text-sm w-44 outline-none"
                      />
                    </div>
                  </div>
                  <p className="px-5 py-2 text-xs text-mute border-b border-line">{CRM_TAB_META[crmTab].hint}</p>
                  {decorated.length === 0 ? (
                    <p className="px-5 py-12 text-center text-sm text-mute">
                      The board is empty. After you subscribe and the packet is in, cycle 1 places people on Cold. Cycle 2 writes from there.
                    </p>
                  ) : filtered.length === 0 ? (
                    <p className="px-5 py-12 text-center text-sm text-mute">No leads on this tab match the search.</p>
                  ) : (
                    <ul>
                      {filtered.map((item) => (
                        <li
                          key={item.case_id}
                          role="button"
                          tabIndex={0}
                          onClick={() => openLead(item.case_id, item.crmTab)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              openLead(item.case_id, item.crmTab);
                            }
                          }}
                          className="px-5 py-4 border-b border-[#F0EFE9] last:border-0 cursor-pointer"
                          style={{ backgroundColor: selected?.case_id === item.case_id ? "#FFE8E1" : "transparent" }}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0">
                              <div className="text-sm font-semibold truncate">{item.lead.name || "Unnamed lead"}</div>
                              <div className="text-sm text-mute truncate mt-0.5">
                                {item.category ?? "Uncategorized"}
                                {item.lead.region ? ` · ${item.lead.region}` : ""}
                              </div>
                            </div>
                            <span className="text-[11px] text-clay flex items-center gap-1 shrink-0">
                              <Clock size={11} /> {formatRelativeTime(item.updated_at)}
                            </span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <aside className="w-full xl:w-[420px] shrink-0 bg-white rounded-2xl border border-line flex flex-col min-h-[420px] xl:sticky xl:top-6">
                  {!selected ? (
                    <p className="text-sm text-mute p-6">Select a lead to watch the thread.</p>
                  ) : (
                    <>
                      <div className="px-5 py-4 border-b border-line">
                        <h2 className="text-lg font-semibold">{selected.lead.name || "Unnamed lead"}</h2>
                        <p className="text-xs text-mute mt-1">{CRM_TAB_META[selected.crmTab].label} · watch only</p>
                        <div className="mt-3 flex flex-wrap gap-3 text-xs text-mute">
                          <span className="flex items-center gap-1.5"><Phone size={12} /> {selected.lead.phone || "Not on file"}</span>
                          <span className="flex items-center gap-1.5"><Mail size={12} /> {selected.lead.email || "Not on file"}</span>
                        </div>
                      </div>
                      <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3 max-h-[560px]">
                        {threadLoading && (
                          <div className="text-sm text-mute flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Opening thread…</div>
                        )}
                        {!threadLoading && threadMissing && (
                          <p className="text-sm text-mute">No conversation yet. Cold stays quiet until cycle 2 writes.</p>
                        )}
                        {thread?.messages.map((message) => (
                          <div key={message.message_id} className={`flex flex-col ${message.direction === "inbound" ? "items-start" : "items-end"}`}>
                            <div
                              className="text-sm max-w-[90%] px-3.5 py-2.5 rounded-2xl"
                              style={message.direction === "inbound" ? { backgroundColor: "#F1F1EF" } : { backgroundColor: "#FFE4D6" }}
                            >
                              {message.text}
                            </div>
                            <span className="text-[10px] text-clay mt-1">
                              {message.role === "customer" ? selected.lead.name || "Lead" : "Engine"} · {formatRelativeTime(message.created_at)}
                            </span>
                          </div>
                        ))}
                        {thread && thread.messages.length === 0 && !threadLoading && (
                          <p className="text-sm text-mute">The thread is open. No lines yet.</p>
                        )}
                      </div>
                    </>
                  )}
                </aside>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
