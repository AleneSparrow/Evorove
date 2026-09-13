import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  api,
  type DashboardAnalytics,
  type DashboardCaseSummary,
  type DashboardConversationSummary,
  type ReportingSettings,
  type ReportingSettingsUpdate,
} from "../api/client";
import { describeError } from "../auth/AuthContext";
import { isoToUs, usToIso } from "../lib/usDate";
import {
  CONVERSATION_STATUS_LABELS,
  ESCALATION_LABELS,
} from "../lib/escalationCopy";
import { CRM_TAB_META, ENGAGEMENT_LABEL, engagementBand, mapCrmTab, type CrmTab, type EngagementBand } from "../lib/crmBoard";
import { formatRelativeTime } from "./Shared";

function UsDateField({ label, value, min, onChange }: {
  label: string;
  value: string;
  min?: string;
  onChange: (iso: string) => void;
}) {
  const [text, setText] = useState(() => isoToUs(value));
  const [invalid, setInvalid] = useState(false);

  useEffect(() => {
    setText(isoToUs(value));
    setInvalid(false);
  }, [value]);

  const commit = (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed) {
      setInvalid(false);
      onChange("");
      return;
    }
    const iso = usToIso(trimmed);
    if (!iso || (min && iso < min)) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    onChange(iso);
  };

  return (
    <label className="text-xs text-mute flex flex-col gap-1">
      {label}
      <input
        type="text"
        inputMode="numeric"
        lang="en-US"
        autoComplete="off"
        placeholder="MM/DD/YYYY"
        aria-label={`${label} date, month slash day slash year`}
        aria-invalid={invalid}
        value={text}
        onChange={(event) => { setText(event.target.value); setInvalid(false); }}
        onBlur={(event) => commit(event.target.value)}
        onKeyDown={(event) => { if (event.key === "Enter") commit((event.target as HTMLInputElement).value); }}
        className="w-[118px] px-2.5 py-2 rounded-lg border text-sm text-ink outline-none"
        style={{ borderColor: invalid ? "#B4483A" : "#E4DCCB" }}
      />
    </label>
  );
}

function StatCard({ label, value, sub, tone, emphasis = false }: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: string;
  emphasis?: boolean;
}) {
  return (
    <div className={`rounded-2xl border px-4 py-3 min-w-0 ${emphasis ? "border-lime bg-lime-wash" : "border-line bg-white"}`}>
      <div className="font-medium text-mute text-[11px] leading-tight mb-1">{label}</div>
      <span className="ev-display text-[28px] leading-none block">
        {value}
      </span>
      {sub && (
        <span className="text-[11px] leading-tight block mt-1 break-words font-medium" style={{ color: tone || "#6B6459" }}>
          {sub}
        </span>
      )}
    </div>
  );
}

function MetricBars({
  leftLabel,
  leftValue,
  rightLabel,
  rightValue,
}: {
  leftLabel: string;
  leftValue: number;
  rightLabel: string;
  rightValue: number;
}) {
  const max = Math.max(leftValue, rightValue, 1);
  return (
    <div className="space-y-3">
      {[{ label: leftLabel, value: leftValue }, { label: rightLabel, value: rightValue }].map((row) => (
        <div key={row.label}>
          <div className="flex justify-between text-xs text-mute mb-1">
            <span>{row.label}</span>
            <span className="ev-display text-lg text-ink leading-none">{row.value}</span>
          </div>
          <div className="h-3 rounded-full bg-[#F1F1EF] overflow-hidden">
            <div className="h-full rounded-full" style={{ width: `${Math.round((row.value / max) * 100)}%`, backgroundColor: "#FF5A36" }} />
          </div>
        </div>
      ))}
    </div>
  );
}
type LeadSort = "date" | "name" | "region" | "gender" | "engagement";
type ConversationSort = "date" | "name" | "status" | "channel";
type SortDirection = "asc" | "desc";

function SortButton({
  label,
  active,
  direction,
  onClick,
}: {
  label: string;
  active: boolean;
  direction: SortDirection;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 text-left font-medium"
      style={{ color: active ? "#0B0B0D" : "#6B6459" }}
  >
      {label}
      {active && (direction === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
    </button>
  );
}

function inPeriod(iso: string, startDate: string, endDate: string): boolean {
  const day = iso.slice(0, 10);
  if (startDate && day < startDate) return false;
  if (endDate && day > endDate) return false;
  return true;
}

export function StatisticsPanel({
  token,
  businessId,
  reporting,
  reportingSaving,
  reportingError,
  onUpdateReporting,
}: {
  token: string;
  businessId: string;
  reporting: ReportingSettings | null;
  reportingSaving: boolean;
  reportingError: string | null;
  onUpdateReporting: (update: ReportingSettingsUpdate) => Promise<boolean | void>;
}) {
  const navigate = useNavigate();
  const [analytics, setAnalytics] = useState<DashboardAnalytics | null>(null);
  const [cases, setCases] = useState<DashboardCaseSummary[] | null>(null);
  const [conversations, setConversations] = useState<DashboardConversationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [includeTestData, setIncludeTestData] = useState(false);
  const [statsVersion, setStatsVersion] = useState(0);
  const [confirmingReset, setConfirmingReset] = useState(false);
  const [leadSort, setLeadSort] = useState<LeadSort>("date");
  const [leadDirection, setLeadDirection] = useState<SortDirection>("desc");
  const [conversationSort, setConversationSort] = useState<ConversationSort>("date");
  const [conversationDirection, setConversationDirection] = useState<SortDirection>("desc");
  const [leadTabFilter, setLeadTabFilter] = useState<CrmTab | "ALL">("ALL");
  const [genderFilter, setGenderFilter] = useState("ALL");
  const [regionFilter, setRegionFilter] = useState("ALL");
  const [engagementFilter, setEngagementFilter] = useState<EngagementBand | "ALL">("ALL");
  const [conversationStatusFilter, setConversationStatusFilter] = useState<string>("ALL");
  const [showCharts, setShowCharts] = useState(false);
  const [chartX, setChartX] = useState<"leads" | "cold" | "conversations">("leads");
  const [chartY, setChartY] = useState<"done" | "in_progress" | "offer_made" | "engine">("done");

  useEffect(() => {
    let cancelled = false;
    setError(null);
    const scope = {
      startDate: startDate || undefined,
      endDate: endDate || undefined,
      includeTest: includeTestData,
    };
    Promise.all([
      api.getDashboardAnalytics(token, businessId, scope),
      api.listCases(token, businessId, scope),
      api.listConversations(token, businessId),
    ])
      .then(([nextAnalytics, caseList, conversationList]) => {
        if (cancelled) return;
        setAnalytics(nextAnalytics);
        setCases(caseList.cases);
        setConversations(conversationList.conversations);
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err));
      });
    return () => {
      cancelled = true;
    };
  }, [token, businessId, startDate, endDate, includeTestData, statsVersion]);

  const decoratedLeads = useMemo(
    () =>
      (cases ?? []).map((c) => ({
        ...c,
        crmTab: mapCrmTab(c.current_state),
        engagement: engagementBand(c.event_count, c.updated_at),
      })),
    [cases],
  );

  const tabCounts = useMemo(() => {
    const next = { cold: 0, in_progress: 0, offer_made: 0, done: 0, lost: 0 };
    decoratedLeads.forEach((item) => {
      next[item.crmTab] += 1;
    });
    return next;
  }, [decoratedLeads]);

  const genders = useMemo(
    () => Array.from(new Set(decoratedLeads.map((item) => item.lead.gender).filter((value): value is string => Boolean(value)))),
    [decoratedLeads],
  );
  const regions = useMemo(
    () => Array.from(new Set(decoratedLeads.map((item) => item.lead.region).filter((value): value is string => Boolean(value)))),
    [decoratedLeads],
  );

  const periodConversations = useMemo(
    () =>
      (conversations ?? []).filter((conversation) => {
        if (!includeTestData) {
          const linked = (cases ?? []).find((c) => c.case_id === conversation.case_id);
          if (linked?.is_test) return false;
        }
        return inPeriod(conversation.last_activity_at, startDate, endDate);
      }),
    [conversations, cases, includeTestData, startDate, endDate],
  );

  const conversationCounts = useMemo(() => {
    const counts = { total: 0, engine: 0, closed: 0, sms: 0, web: 0 };
    periodConversations.forEach((conversation) => {
      counts.total += 1;
      if (conversation.status === "ai_active") counts.engine += 1;
      if (conversation.status === "closed") counts.closed += 1;
      if (conversation.channel === "sms") counts.sms += 1;
      else counts.web += 1;
    });
    return counts;
  }, [periodConversations]);

  const sortedLeads = useMemo(() => {
    const visible = decoratedLeads.filter((c) => {
      if (leadTabFilter !== "ALL" && c.crmTab !== leadTabFilter) return false;
      if (genderFilter !== "ALL" && (c.lead.gender || "Unknown") !== genderFilter) return false;
      if (regionFilter !== "ALL" && (c.lead.region || "Unknown") !== regionFilter) return false;
      if (engagementFilter !== "ALL" && c.engagement !== engagementFilter) return false;
      return true;
    });
    return visible.sort((left, right) => {
      let comparison = 0;
      if (leadSort === "date") comparison = new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
      else if (leadSort === "name") comparison = (left.lead.name || "").localeCompare(right.lead.name || "", undefined, { sensitivity: "base" });
      else if (leadSort === "region") comparison = (left.lead.region || "").localeCompare(right.lead.region || "", undefined, { sensitivity: "base" });
      else if (leadSort === "gender") comparison = (left.lead.gender || "").localeCompare(right.lead.gender || "", undefined, { sensitivity: "base" });
      else comparison = left.event_count - right.event_count;
      return leadDirection === "asc" ? comparison : -comparison;
    });
  }, [decoratedLeads, leadTabFilter, genderFilter, regionFilter, engagementFilter, leadSort, leadDirection]);

  const sortedConversations = useMemo(() => {
    const visible = periodConversations.filter((conversation) => (
      conversationStatusFilter === "ALL" || conversation.status === conversationStatusFilter
    ));
    return visible.sort((left, right) => {
      let comparison = 0;
      if (conversationSort === "date") comparison = new Date(left.last_activity_at).getTime() - new Date(right.last_activity_at).getTime();
      else if (conversationSort === "name") comparison = (left.lead_name || "").localeCompare(right.lead_name || "", undefined, { sensitivity: "base" });
      else if (conversationSort === "status") comparison = left.status.localeCompare(right.status);
      else comparison = left.channel.localeCompare(right.channel);
      return conversationDirection === "asc" ? comparison : -comparison;
    });
  }, [periodConversations, conversationStatusFilter, conversationSort, conversationDirection]);

  const toggleLeadSort = (next: LeadSort) => {
    if (leadSort === next) setLeadDirection((current) => (current === "asc" ? "desc" : "asc"));
    else {
      setLeadSort(next);
      setLeadDirection(next === "date" || next === "engagement" ? "desc" : "asc");
    }
  };

  const toggleConversationSort = (next: ConversationSort) => {
    if (conversationSort === next) setConversationDirection((current) => (current === "asc" ? "desc" : "asc"));
    else {
      setConversationSort(next);
      setConversationDirection(next === "name" || next === "status" || next === "channel" ? "asc" : "desc");
    }
  };

  const resetStatistics = async () => {
    const ok = await onUpdateReporting({ reset_statistics: true });
    setConfirmingReset(false);
    if (ok !== false) setStatsVersion((current) => current + 1);
  };

  const restoreHistory = async () => {
    const ok = await onUpdateReporting({ clear_statistics_baseline: true });
    if (ok !== false) setStatsVersion((current) => current + 1);
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-2xl border p-5" style={{ borderColor: "#E4DCCB" }}>
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="text-base font-semibold">Reporting period</h2>
            <p className="text-sm text-mute mt-1">Filter every figure and table below by when the lead or conversation was created.</p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <UsDateField label="From" value={startDate} onChange={setStartDate} />
            <UsDateField label="To" value={endDate} min={startDate} onChange={setEndDate} />
            {(startDate || endDate) && (
              <button type="button" onClick={() => { setStartDate(""); setEndDate(""); }} className="text-xs font-medium px-3 py-2 rounded-lg border border-line hover:border-coral transition-colors">
                All time
              </button>
            )}
          </div>
        </div>
        {analytics && analytics.hidden_test_cases > 0 && (
          <label className="text-xs text-mute flex items-center gap-2 mb-4">
            <input type="checkbox" checked={includeTestData} onChange={(event) => setIncludeTestData(event.target.checked)} className="accent-coral" />
            {includeTestData
              ? "Including test data"
              : `Test data hidden · ${analytics.hidden_test_conversations} conversations / ${analytics.hidden_test_cases} cases`}
          </label>
        )}
        <h3 className="text-sm font-semibold mb-1">Statistics baseline</h3>
        <p className="text-sm text-mute leading-relaxed">
          Resetting starts these metrics from now. It never deletes conversations, cases, or audit events. You can restore the full history at any time.
        </p>
        <p className="text-xs text-mute mt-2" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
          {reporting?.stats_since ? `Counting cases created since ${new Date(reporting.stats_since).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" })}` : "Counting all retained history"}
        </p>
        <div className="flex flex-wrap gap-2 mt-4">
          {confirmingReset ? (
            <>
              <button type="button" onClick={() => void resetStatistics()} disabled={reportingSaving} className="text-sm font-medium px-4 py-2.5 rounded-lg border border-coral text-coral-deep bg-coral-wash disabled:opacity-50">
                {reportingSaving ? "Resetting…" : "Confirm reset"}
              </button>
              <button type="button" onClick={() => setConfirmingReset(false)} className="text-sm font-medium px-4 py-2.5 rounded-lg border border-line">
                Cancel
              </button>
            </>
          ) : (
            <button type="button" onClick={() => setConfirmingReset(true)} disabled={!reporting || reportingSaving} className="text-sm font-medium px-4 py-2.5 rounded-lg border border-line disabled:opacity-50">
              Reset statistics
            </button>
          )}
          {reporting?.stats_since && (
            <button type="button" onClick={() => void restoreHistory()} disabled={reportingSaving} className="text-sm font-medium px-4 py-2.5 rounded-lg border border-line disabled:opacity-50">
              Restore full history
            </button>
          )}
        </div>
        {reportingError && (
          <div className="mt-4 px-4 py-3 rounded-lg text-sm" style={{ backgroundColor: "#FBEBE9", color: "#8A3225" }}>
            {reportingError}
          </div>
        )}
      </div>

      {error && (
        <div className="px-4 py-3 rounded-lg text-sm" style={{ backgroundColor: "#FBEBE9", color: "#8A3225" }}>
          Couldn't load statistics: {error}
        </div>
      )}

      {cases === null && !error ? (
        <div className="flex items-center gap-2 text-sm text-mute py-8 justify-center">
          <Loader2 size={16} className="animate-spin" /> Loading statistics…
        </div>
      ) : (
        <>
          <div>
            <div className="flex flex-wrap items-end justify-between gap-3 mb-3">
              <div>
                <h2 className="text-base font-semibold">Business metrics</h2>
                <p className="text-sm text-mute">Counts and rates a bookkeeper can read. No conversion promise.</p>
              </div>
              <button
                type="button"
                onClick={() => setShowCharts((current) => !current)}
                className="text-sm font-medium px-4 py-2 rounded-lg border border-line"
              >
                Visualization
              </button>
            </div>
            <div className="grid gap-2 grid-cols-2 md:grid-cols-3">
              <StatCard label="Leads" value={analytics?.total_cases ?? decoratedLeads.length} sub="headcount in period" />
              <StatCard label="Cold" value={tabCounts.cold} sub="not written yet" />
              <StatCard label="In progress" value={tabCounts.in_progress} sub="engine on the thread" tone="#FF5A36" />
              <StatCard label="Offer made" value={tabCounts.offer_made} sub="value named" tone="#FF5A36" />
              <StatCard label="Done" value={tabCounts.done} sub="sale or booked hour" tone="#1E7B52" />
              <StatCard
                label="Human review"
                value={analytics?.human_review_cases ?? 0}
                sub="STOP, emergency, or policy — out of conversion"
              />
              <StatCard
                label="Done rate"
                value={
                  analytics && analytics.conversion_eligible_cases
                    ? `${Math.round(analytics.booking_conversion_rate * 100)}%`
                    : "—"
                }
                sub={
                  analytics
                    ? `${analytics.booked_cases} booked / ${analytics.conversion_eligible_cases} eligible`
                    : "human review excluded"
                }
              />
              <StatCard label="Lost" value={analytics?.lost_cases ?? tabCounts.lost} sub={analytics ? `${Math.round(analytics.lost_rate * 100)}% of leads` : undefined} />
              <StatCard label="Booked events" value={analytics?.booked_cases ?? 0} sub="hour set in history" tone="#1E7B52" />
            </div>
          </div>

          {showCharts && (
            <div className="rounded-2xl border p-5" style={{ borderColor: "#E4DCCB" }}>
              <h2 className="text-base font-semibold mb-1">Build a chart</h2>
              <p className="text-sm text-mute mb-4">Pick two series. Bars use the numbers already on this page.</p>
              <div className="flex flex-wrap gap-3 mb-4">
                <label className="text-xs text-mute">X
                  <select className="ml-2 border border-line rounded-lg px-2 py-1.5 text-sm" value={chartX} onChange={(event) => setChartX(event.target.value as typeof chartX)}>
                    <option value="leads">Leads</option>
                    <option value="cold">Cold</option>
                    <option value="conversations">Conversations</option>
                  </select>
                </label>
                <label className="text-xs text-mute">Y
                  <select className="ml-2 border border-line rounded-lg px-2 py-1.5 text-sm" value={chartY} onChange={(event) => setChartY(event.target.value as typeof chartY)}>
                    <option value="done">Done</option>
                    <option value="offer_made">Offer made</option>
                    <option value="in_progress">In progress</option>
                    <option value="engine">Engine threads</option>
                  </select>
                </label>
              </div>
              <MetricBars
                leftLabel={chartX === "leads" ? "Leads" : chartX === "cold" ? "Cold" : "Conversations"}
                leftValue={chartX === "leads" ? decoratedLeads.length : chartX === "cold" ? tabCounts.cold : conversationCounts.total}
                rightLabel={chartY === "done" ? "Done" : chartY === "offer_made" ? "Offer made" : chartY === "in_progress" ? "In progress" : "Engine threads"}
                rightValue={chartY === "done" ? tabCounts.done : chartY === "offer_made" ? tabCounts.offer_made : chartY === "in_progress" ? tabCounts.in_progress : conversationCounts.engine}
              />
            </div>
          )}

          <div>
            <h2 className="text-base font-semibold mb-3">Conversations</h2>
            <div className="grid gap-2 grid-cols-2 md:grid-cols-3">
              <StatCard label="Conversations" value={conversationCounts.total} sub="by last activity" />
              <StatCard label="Engine handling" value={conversationCounts.engine} sub="still on the thread" />
              <StatCard label="Closed threads" value={conversationCounts.closed} />
              <StatCard label="Website" value={conversationCounts.web} sub="web chat" />
              <StatCard label="SMS" value={conversationCounts.sms} sub="text message" />
              <StatCard
                label="Median first response"
                value={analytics?.median_first_response_seconds != null ? `${Math.round(analytics.median_first_response_seconds)}s` : "—"}
                sub={analytics ? `${analytics.response_samples} samples` : undefined}
                tone="#1E7B52"
              />
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-line overflow-hidden">
            <div className="px-5 py-3 border-b border-line flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Leads ({sortedLeads.length})</h2>
              <div className="flex flex-wrap gap-1.5">
                {(["ALL", "cold", "in_progress", "offer_made", "done", "lost"] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setLeadTabFilter(tab)}
                    className="px-2.5 py-1 rounded-full text-[11px] font-medium"
                    style={{ backgroundColor: leadTabFilter === tab ? "#FFE8E1" : "transparent", color: leadTabFilter === tab ? "#FF5A36" : "#6B6459" }}
                  >
                    {tab === "ALL" ? "All" : CRM_TAB_META[tab].label}
                  </button>
                ))}
              </div>
            </div>
            <div className="px-5 py-3 flex flex-wrap gap-2 border-b border-line">
              <select aria-label="Filter by gender" className="border border-line rounded-lg px-2 py-1.5 text-xs" value={genderFilter} onChange={(event) => setGenderFilter(event.target.value)}>
                <option value="ALL">Gender: all</option>
                <option value="Unknown">Unknown</option>
                {genders.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
              <select aria-label="Filter by region" className="border border-line rounded-lg px-2 py-1.5 text-xs" value={regionFilter} onChange={(event) => setRegionFilter(event.target.value)}>
                <option value="ALL">Region: all</option>
                <option value="Unknown">Unknown</option>
                {regions.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
              <select aria-label="Filter by engagement" className="border border-line rounded-lg px-2 py-1.5 text-xs" value={engagementFilter} onChange={(event) => setEngagementFilter(event.target.value as EngagementBand | "ALL")}>
                <option value="ALL">Engagement: all</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wide border-b border-line">
                    <th className="text-left px-5 py-2 font-medium"><SortButton label="Lead" active={leadSort === "name"} direction={leadDirection} onClick={() => toggleLeadSort("name")} /></th>
                    <th className="text-left px-3 py-2 font-medium"><SortButton label="Added" active={leadSort === "date"} direction={leadDirection} onClick={() => toggleLeadSort("date")} /></th>
                    <th className="text-left px-3 py-2 font-medium"><SortButton label="Gender" active={leadSort === "gender"} direction={leadDirection} onClick={() => toggleLeadSort("gender")} /></th>
                    <th className="text-left px-3 py-2 font-medium"><SortButton label="Region" active={leadSort === "region"} direction={leadDirection} onClick={() => toggleLeadSort("region")} /></th>
                    <th className="text-left px-3 py-2 font-medium"><SortButton label="Engagement" active={leadSort === "engagement"} direction={leadDirection} onClick={() => toggleLeadSort("engagement")} /></th>
                    <th className="text-left px-3 py-2 font-medium text-mute">Tab</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedLeads.length === 0 && (
                    <tr><td colSpan={6} className="px-5 py-8 text-center text-mute">No leads in this period match the filters. Gender and region appear only when they were recorded — they are never guessed.</td></tr>
                  )}
                  {sortedLeads.map((c) => (
                    <tr key={c.case_id} className="border-b border-[#F0EFE9] last:border-0 cursor-pointer hover:bg-[#FAFAF7]" onClick={() => navigate(`/app?view=board&lead=${encodeURIComponent(c.case_id)}`)}>
                      <td className="px-5 py-3 font-medium">{c.lead.name || "Unnamed lead"}</td>
                      <td className="px-3 py-3 text-mute">{formatRelativeTime(c.created_at)}</td>
                      <td className="px-3 py-3 text-mute">{c.lead.gender || "Unknown"}</td>
                      <td className="px-3 py-3 text-mute">{c.lead.region || "Unknown"}</td>
                      <td className="px-3 py-3">{ENGAGEMENT_LABEL[c.engagement]}</td>
                      <td className="px-3 py-3 text-mute">{CRM_TAB_META[c.crmTab].label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-line overflow-hidden">
            <div className="px-5 py-3 border-b border-line flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Conversations in this period ({sortedConversations.length})</h2>
              <div className="flex flex-wrap gap-1.5">
                {["ALL", "ai_active", "human_takeover_requested", "human_takeover_active", "closed"].map((status) => (
                  <button
                    key={status}
                    type="button"
                    onClick={() => setConversationStatusFilter(status)}
                    className="px-2.5 py-1 rounded-full text-[11px] font-medium"
                    style={{ backgroundColor: conversationStatusFilter === status ? "#FFE8E1" : "transparent", color: conversationStatusFilter === status ? "#FF5A36" : "#6B6459" }}
                >
                    {status === "ALL" ? "All" : CONVERSATION_STATUS_LABELS[status]}
                  </button>
                ))}
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[11px] uppercase tracking-wide border-b border-line">
                    <th className="text-left px-5 py-2 font-medium"><SortButton label="Lead" active={conversationSort === "name"} direction={conversationDirection} onClick={() => toggleConversationSort("name")} /></th>
                    <th className="text-left px-3 py-2 font-medium"><SortButton label="Activity" active={conversationSort === "date"} direction={conversationDirection} onClick={() => toggleConversationSort("date")} /></th>
                    <th className="text-left px-3 py-2 font-medium"><SortButton label="Status" active={conversationSort === "status"} direction={conversationDirection} onClick={() => toggleConversationSort("status")} /></th>
                    <th className="text-left px-3 py-2 font-medium"><SortButton label="Channel" active={conversationSort === "channel"} direction={conversationDirection} onClick={() => toggleConversationSort("channel")} /></th>
                    <th className="text-left px-3 py-2 font-medium text-mute">Attention</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedConversations.length === 0 && (
                    <tr><td colSpan={5} className="px-5 py-8 text-center text-mute">No conversations in this period match the filters.</td></tr>
                  )}
                  {sortedConversations.map((conversation) => (
                    <tr
                      key={conversation.conversation_id}
                      className="border-b border-[#F0EFE9] last:border-0 cursor-pointer hover:bg-[#FAFAF7]"
                      onClick={() => {
                        if (!conversation.case_id) {
                          navigate("/app/conversations");
                          return;
                        }
                        if (conversation.status.startsWith("human")) {
                          navigate(`/app/conversations?case=${encodeURIComponent(conversation.case_id)}`);
                          return;
                        }
                        navigate(`/app?view=board&lead=${encodeURIComponent(conversation.case_id)}`);
                      }}
                    >
                      <td className="px-5 py-3 font-medium">{conversation.lead_name || "Unnamed lead"}</td>
                      <td className="px-3 py-3 text-mute">{formatRelativeTime(conversation.last_activity_at)}</td>
                      <td className="px-3 py-3">{CONVERSATION_STATUS_LABELS[conversation.status]}</td>
                      <td className="px-3 py-3 text-mute">{conversation.channel}</td>
                      <td className="px-3 py-3 text-mute">{ESCALATION_LABELS[conversation.escalation_reason ?? ""] ?? (conversation.status.startsWith("human") ? "Safety stop" : "—")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
