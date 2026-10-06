import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, Clock, Loader2, Phone, Mail } from "lucide-react";
import { Sidebar } from "../components/Sidebar";
import { MaterialsPanel } from "../components/MaterialsPanel";
import { StatisticsPanel } from "../components/StatisticsPanel";
import { FindPeople } from "../components/FindPeople";
import { useAuth, describeError } from "../auth/AuthContext";
import {
  api,
  type BoardPerson,
  type BoardPersonDetail,
  type BoardTouch,
  type ReportingSettings,
  type ReportingSettingsUpdate,
} from "../api/client";
import {
  BOARD_API_TABS,
  CRM_BOARD_TABS,
  CRM_TAB_META,
  mapBoardApiTab,
  type WatchTab,
} from "../lib/crmBoard";
import { formatRelativeTime } from "../components/Shared";

const BOARD_VIEWS = ["board", "statistics", "materials"] as const;
type PageView = (typeof BOARD_VIEWS)[number];
const WRITTEN_KINDS = new Set(["dialogue_started", "message", "offer_sent", "ready_to_book", "booked", "paid"]);

function isPageView(value: string | null): value is PageView {
  return value !== null && (BOARD_VIEWS as readonly string[]).includes(value);
}

function personLabel(person: BoardPerson): string {
  return person.name || person.email || person.phone || "Unnamed lead";
}

function engineHasWritten(touches: BoardTouch[]): boolean {
  return touches.some((touch) => WRITTEN_KINDS.has(touch.kind));
}

function touchIsInbound(touch: BoardTouch): boolean {
  return touch.payload.direction === "inbound" || touch.summary.startsWith("Customer:");
}

export default function Dashboard() {
  const { token, businessId } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const pageTab: PageView = isPageView(searchParams.get("view")) ? searchParams.get("view") as PageView : "board";
  const requestedPerson = searchParams.get("lead");
  const [people, setPeople] = useState<BoardPerson[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [crmTab, setCrmTab] = useState<WatchTab>("cold");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<BoardPersonDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reporting, setReporting] = useState<ReportingSettings | null>(null);
  const [reportingSaving, setReportingSaving] = useState(false);
  const [reportingError, setReportingError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reloadPeople = useCallback(() => setReloadKey((key) => key + 1), []);

  useEffect(() => {
    let cancelled = false;
    if (!token || !businessId) return;
    Promise.all(BOARD_API_TABS.map((tab) => api.listBoard(token, businessId, tab)))
      .then((pages) => {
        if (cancelled) return;
        const listed = pages.flatMap((page) => page.people);
        setPeople(listed);
        const fromUrl = requestedPerson
          ? listed.find((item) => item.person_id === requestedPerson)
          : undefined;
        const pick = fromUrl ?? listed[0];
        if (pick) {
          setSelectedId(pick.person_id);
          setCrmTab(mapBoardApiTab(pick.tab === "discarded" ? "cold" : pick.tab));
        }
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [token, businessId, requestedPerson, reloadKey]);

  useEffect(() => {
    if (!token || !businessId) return;
    api.getReportingSettings(token, businessId).then(setReporting).catch((err) => setReportingError(describeError(err)));
  }, [token, businessId]);

  const setPageTab = (next: PageView) => {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set("view", next);
      if (selectedId) params.set("lead", selectedId);
      return params;
    }, { replace: true });
  };

  const openPerson = (personId: string, tab: WatchTab) => {
    setSelectedId(personId);
    setCrmTab(tab);
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set("view", "board");
      params.set("lead", personId);
      return params;
    }, { replace: true });
  };

  const counts = useMemo(() => {
    const next: Record<WatchTab, number> = { cold: 0, in_progress: 0, offer_made: 0, done: 0 };
    (people ?? []).forEach((item) => {
      if (item.tab === "discarded") return;
      next[mapBoardApiTab(item.tab)] += 1;
    });
    return next;
  }, [people]);

  const filtered = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return (people ?? []).filter((item) => {
      if (item.tab === "discarded") return false;
      if (mapBoardApiTab(item.tab) !== crmTab) return false;
      if (!query) return true;
      return [item.name, item.phone, item.email, item.summary, item.person_id]
        .some((value) => value?.toLowerCase().includes(query));
    });
  }, [people, crmTab, searchQuery]);

  const selected = useMemo(
    () => (people ?? []).find((item) => item.person_id === selectedId) ?? null,
    [people, selectedId],
  );

  useEffect(() => {
    let cancelled = false;
    if (!token || !businessId || !selectedId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    api
      .getBoardPerson(token, businessId, selectedId)
      .then((res) => {
        if (!cancelled) setDetail(res);
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err));
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
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

  const selectedTab = selected && selected.tab !== "discarded" ? mapBoardApiTab(selected.tab) : crmTab;

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
              ["materials", "Materials"],
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
            {people === null && !error ? (
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
                  {crmTab === "cold" && <FindPeople onFound={reloadPeople} />}
                  {(people ?? []).length === 0 ? (
                    <p className="px-5 py-12 text-center text-sm text-mute">
                      The board is empty. After you subscribe and set up the business, the engine finds people and puts them on Cold. Then it writes to them.
                    </p>
                  ) : filtered.length === 0 ? (
                    <p className="px-5 py-12 text-center text-sm text-mute">No people on this tab match the search.</p>
                  ) : (
                    <ul>
                      {filtered.map((item) => (
                        <li
                          key={item.person_id}
                          role="button"
                          tabIndex={0}
                          onClick={() => openPerson(item.person_id, mapBoardApiTab(item.tab === "discarded" ? "cold" : item.tab))}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              openPerson(item.person_id, mapBoardApiTab(item.tab === "discarded" ? "cold" : item.tab));
                            }
                          }}
                          className="px-5 py-4 border-b border-[#F0EFE9] last:border-0 cursor-pointer"
                          style={{ backgroundColor: selected?.person_id === item.person_id ? "#FFE8E1" : "transparent" }}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0">
                              <div className="text-sm font-semibold truncate">{personLabel(item)}</div>
                              <div className="text-sm text-mute truncate mt-0.5">{item.summary}</div>
                            </div>
                            <span className="text-[11px] text-clay flex items-center gap-1 shrink-0">
                              <Clock size={11} /> {formatRelativeTime(item.last_touch_at)}
                            </span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <aside className="w-full xl:w-[420px] shrink-0 bg-white rounded-2xl border border-line flex flex-col min-h-[420px] xl:sticky xl:top-6">
                  {!selected ? (
                    <p className="text-sm text-mute p-6">Select a person to watch the thread.</p>
                  ) : (
                    <>
                      <div className="px-5 py-4 border-b border-line">
                        <h2 className="text-lg font-semibold">{personLabel(selected)}</h2>
                        <p className="text-xs text-mute mt-1">{CRM_TAB_META[selectedTab].label} · watch only</p>
                        <div className="mt-3 flex flex-wrap gap-3 text-xs text-mute">
                          <span className="flex items-center gap-1.5"><Phone size={12} /> {selected.phone || "Not on file"}</span>
                          <span className="flex items-center gap-1.5"><Mail size={12} /> {selected.email || "Not on file"}</span>
                        </div>
                      </div>
                      <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3 max-h-[560px]">
                        {detailLoading && (
                          <div className="text-sm text-mute flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Opening thread…</div>
                        )}
                        {!detailLoading && detail && !engineHasWritten(detail.touches) && (
                          <p className="text-sm text-mute">No conversation yet. The engine has not written.</p>
                        )}
                        {detail?.touches.map((touch) => (
                          <div
                            key={touch.touch_id}
                            className={`flex flex-col ${touch.kind === "message" && touchIsInbound(touch) ? "items-start" : "items-end"}`}
                          >
                            {touch.kind === "message" ? (
                              <div
                                className="text-sm max-w-[90%] px-3.5 py-2.5 rounded-2xl"
                                style={touchIsInbound(touch) ? { backgroundColor: "#F1F1EF" } : { backgroundColor: "#FFE4D6" }}
                              >
                                {touch.summary.replace(/^(Customer|Evorove):\s*/, "")}
                              </div>
                            ) : (
                              <p className="text-xs text-mute">{touch.summary}</p>
                            )}
                            <span className="text-[10px] text-clay mt-1">
                              {touch.kind === "message" && touchIsInbound(touch) ? personLabel(selected) : "Engine"} · {formatRelativeTime(touch.occurred_at)}
                            </span>
                          </div>
                        ))}
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
