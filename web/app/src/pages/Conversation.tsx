import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, Search, Phone, Mail, Loader2, AlertTriangle } from "lucide-react";
import { Sidebar } from "../components/Sidebar";
import { StatePill, Stepper, mapProcessState, describeEvent, formatRelativeTime } from "../components/Shared";
import { ConversationSalesPanel } from "../components/ConversationSalesPanel";
import { CONVERSATION_STATUS_LABELS } from "../lib/escalationCopy";
import { useAuth, describeError } from "../auth/AuthContext";
import {
  api,
  type DashboardConversationSummary,
  type DashboardConversationDetail,
  type DashboardCaseDetail,
} from "../api/client";

/**
 * How loudly a conversation is asking for a person, lowest number first.
 * Safety outranks everything; a case a teammate has already claimed sinks
 * below the ones nobody has touched.
 */
const ESCALATION_URGENCY: Record<string, number> = {
  safety_emergency: 0,
  urgent_request: 1,
  identity_conflict: 2,
  policy_review: 2,
  service_area_uncertain: 2,
  service_unclear: 2,
  low_confidence: 3,
  ai_review: 3,
  already_pending: 4,
};

function conversationPriority(conversation: DashboardConversationSummary): number {
  if (conversation.status === "human_takeover_requested") return -1;
  if (conversation.case_state !== "NEEDS_HUMAN") return 10;
  return ESCALATION_URGENCY[conversation.escalation_reason ?? ""] ?? 5;
}

export default function Conversation() {
  const navigate = useNavigate();
  const { token, businessId } = useAuth();
  const [searchParams] = useSearchParams();
  const requestedCaseId = searchParams.get("case");

  const [conversations, setConversations] = useState<DashboardConversationSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  // Opened from the dashboard bell as ?attention=1, which is the whole point
  // of that control: it must LAND you on a list of only what needs you, not
  // quietly set a filter somewhere you cannot see.
  const [attentionOnly, setAttentionOnly] = useState(searchParams.get("attention") !== "0");
  const [requestedCaseMissing, setRequestedCaseMissing] = useState(false);
  const [detail, setDetail] = useState<DashboardConversationDetail | null>(null);
  const [caseDetail, setCaseDetail] = useState<DashboardCaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [riskDraft, setRiskDraft] = useState("");
  const [riskBusy, setRiskBusy] = useState(false);
  const [riskError, setRiskError] = useState<string | null>(null);

  const refreshDetail = useCallback(
    (conversationId: string) => {
      if (!token || !businessId) return Promise.resolve();
      return api
        .getConversation(token, businessId, conversationId)
        .then((res) => {
          setDetail(res);
          if (res.conversation.case_id) {
            return api
              .getCase(token, businessId, res.conversation.case_id)
              .then((c) => setCaseDetail(c))
              .catch(() => undefined);
          }
          setCaseDetail(null);
        });
    },
    [token, businessId],
  );

  useEffect(() => {
    let cancelled = false;
    if (!token || !businessId) return;
    api
      .listConversations(token, businessId)
      .then((res) => {
        if (cancelled) return;
        setConversations(res.conversations);
        const byCase = requestedCaseId ? res.conversations.find((c) => c.case_id === requestedCaseId) : undefined;
        setRequestedCaseMissing(Boolean(requestedCaseId && !byCase));
        setSelectedId((prev) => (
          requestedCaseId
            ? byCase?.conversation_id ?? null
            : prev ?? res.conversations[0]?.conversation_id ?? null
        ));
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, businessId, requestedCaseId]);

  const filteredConversations = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const matching = (conversations ?? []).filter((conversation) => {
      if (attentionOnly && conversation.case_state !== "NEEDS_HUMAN") return false;
      if (!query) return true;
      return [
        conversation.lead_name,
        conversation.lead_phone,
        conversation.lead_email,
        conversation.case_id,
        conversation.conversation_id,
        conversation.channel,
        conversation.status.replace(/_/g, " "),
      ].some((value) => value?.toLowerCase().includes(query));
    });
    // Most urgent first, newest first inside a tier. Plain recency put a
    // safety message below a routine one that happened to arrive later,
    // which is the opposite of what this list is for.
    return matching.sort((left, right) => {
      const byUrgency = conversationPriority(left) - conversationPriority(right);
      if (byUrgency !== 0) return byUrgency;
      return new Date(right.last_activity_at).getTime() - new Date(left.last_activity_at).getTime();
    });
  }, [attentionOnly, conversations, searchQuery]);

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setCaseDetail(null);
    if (!token || !businessId || !selectedId) return;
    refreshDetail(selectedId).catch((err) => {
      if (!cancelled) setError(describeError(err));
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, businessId, selectedId]);

  useEffect(() => {
    setRiskDraft("");
    setRiskError(null);
  }, [selectedId]);

  const stateInfo = useMemo(() => (caseDetail ? mapProcessState(caseDetail.current_state) : null), [caseDetail]);

  const escalationLabel = detail?.conversation.escalation_reason
    ? ({
        safety_emergency: "Safety or emergency language",
        urgent_request: "Customer requested urgent help",
        low_confidence: "Low confidence in the request",
        service_unclear: "Requested service was unclear",
        ai_review: "AI requested human review",
        service_area_uncertain: "Service area could not be confirmed",
        policy_review: "Business policy requires review",
        identity_conflict: "Contact details match another lead",
        already_pending: "Already waiting for review",
      } as Record<string, string>)[detail.conversation.escalation_reason] ?? "Human review requested"
    : null;

  return (
    <div className="ev-page min-h-screen w-full flex">
      <Sidebar />
      <main className="flex-1 min-w-0 flex flex-col pt-14 md:pt-0">
        <div className="flex-1 min-w-0 flex">
          <div className="w-72 shrink-0 border-r border-line flex flex-col">
            <div className="px-4 py-4 border-b border-line">
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-coral mb-3">Safety</p>
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-clay" />
                <input
                  aria-label="Search safety stops"
                  placeholder="Search safety stops…"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  className="w-full pl-8 pr-3 py-2 rounded-lg bg-white border border-line text-sm outline-none"
                />
              </div>
              <button
                onClick={() => setAttentionOnly((current) => !current)}
                className="mt-2 w-full rounded-lg px-3 py-1.5 text-xs font-medium border border-line"
                style={{ backgroundColor: attentionOnly ? "#C6FF00" : "#fff", color: attentionOnly ? "#0B0B0D" : "#6B6459" }}
            >
                Safety stops only
              </button>
            </div>
            {error && (
              <div className="mx-4 mt-3 px-3 py-2 rounded-lg text-xs" style={{ backgroundColor: "#FBEBE9", color: "#8A3225" }}>
                {error}
              </div>
            )}
            {conversations === null ? (
              !error && (
                <div className="flex items-center gap-2 text-sm text-mute py-8 justify-center">
                  <Loader2 size={16} className="animate-spin" /> Loading…
                </div>
              )
            ) : conversations.length === 0 ? (
              <div className="px-4 py-8 text-sm text-mute text-center">No threads yet. Watch sales on CRM.</div>
            ) : filteredConversations.length === 0 ? (
              <div className="px-4 py-8 text-sm text-mute text-center">
                {attentionOnly ? "No safety stops. Normal sales stay on CRM." : "No threads match the search."}
              </div>
            ) : (
              <ul className="flex-1 overflow-y-auto">
                {filteredConversations.map((c) => {
                  const meta = mapProcessState(c.case_state ?? "NEW_LEAD");
                  return (
                    <li
                      key={c.conversation_id}
                      onClick={() => setSelectedId(c.conversation_id)}
                      className="px-4 py-3.5 border-b border-[#F0EFE9] cursor-pointer"
                      style={{ backgroundColor: c.conversation_id === selectedId ? "#FFE8E1" : "transparent" }}
                  >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-semibold">{c.lead_name || "Unnamed lead"}</span>
                        <span className="text-[11px] text-clay">{formatRelativeTime(c.last_activity_at)}</span>
                      </div>
                      <div className="text-xs text-mute truncate mb-1.5">{c.channel} · {CONVERSATION_STATUS_LABELS[c.status] ?? c.status.replace(/_/g, " ")}</div>
                      {c.case_state && <StatePill state={meta.caseState} />}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="flex-1 min-w-0 flex flex-col">
            {!selectedId ? (
              <div className="flex-1 flex items-center justify-center text-sm text-mute px-6 text-center">
                {conversations === null
                  ? "Loading…"
                  : requestedCaseMissing
                    ? "No conversation is linked to this lead yet. Cold stays quiet until cycle 2 writes."
                    : "Safety stops only. Open a lead from CRM to watch a normal sale."}
              </div>
            ) : !detail ? (
              <div className="flex-1 flex items-center justify-center text-sm text-mute">
                <Loader2 size={16} className="animate-spin mr-2" /> Loading conversation…
              </div>
            ) : (
              <>
                <header className="flex items-center justify-between px-6 py-4 border-b border-line">
                  <div className="flex items-center gap-3">
                    <button onClick={() => navigate("/app")} className="text-mute"><ArrowLeft size={16} /></button>
                    <div>
                      <div className="flex items-center gap-2">
                        <h1 className="text-base font-semibold">{detail.conversation.lead_name || "Unnamed lead"}</h1>
                        <span className="text-[11px] text-clay" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
                          {detail.conversation.case_id ? detail.conversation.case_id.slice(0, 8) : detail.conversation.conversation_id.slice(0, 8)}
                        </span>
                      </div>
                      <p className="text-xs text-mute mt-0.5">{detail.conversation.channel} · {CONVERSATION_STATUS_LABELS[detail.conversation.status] ?? detail.conversation.status.replace(/_/g, " ")}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {stateInfo && <StatePill state={stateInfo.caseState} />}
                    {detail.conversation.case_id ? (
                      <button
                        type="button"
                        onClick={() => {
                          const caseId = detail.conversation.case_id;
                          if (!caseId) return;
                          navigate(`/app?view=board&lead=${encodeURIComponent(caseId)}`);
                        }}
                        className="text-xs font-medium px-3 py-1.5 rounded-full border border-line"
                      >
                        Open on CRM
                      </button>
                    ) : null}
                  </div>
                </header>

                <div className="flex-1 overflow-y-auto px-6 py-6 flex flex-col gap-3">
                  {token && businessId && (
                    <ConversationSalesPanel
                      token={token}
                      businessId={businessId}
                      caseId={detail.conversation.case_id}
                      conversationId={detail.conversation.conversation_id}
                    />
                  )}
                  {detail.messages.length === 0 && (
                    <p className="text-sm text-mute text-center mt-8">No messages in this conversation yet.</p>
                  )}
                  {detail.messages.map((m) => (
                    <div key={m.message_id} className={`flex flex-col ${m.direction === "inbound" ? "items-start" : "items-end"}`}>
                      <div
                        className={`text-sm max-w-md px-3.5 py-2.5 rounded-2xl ${m.direction === "inbound" ? "rounded-bl-sm" : "rounded-br-sm"}`}
                        style={m.direction === "inbound" ? { backgroundColor: "#F1F1EF" } : { backgroundColor: "#FFE4D6", color: "#0B0B0D" }}
                    >
                        {m.text}
                      </div>
                      <span className="text-[10px] text-clay mt-1 px-1">
                        {m.role === "customer" ? detail.conversation.lead_name || "Customer" : m.role === "human" ? "You" : "Engine"} · {formatRelativeTime(m.created_at)}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="border-t border-line p-4">
                  {escalationLabel && (
                    <div className="mb-3 rounded-xl border border-[#E8CFAF] bg-[#FFF8EE] p-3">
                      <div className="flex items-center gap-2 text-xs font-semibold text-[#8A561B]">
                        <AlertTriangle size={14} /> Safety or policy stop
                      </div>
                      <p className="mt-1 text-sm text-mute">{escalationLabel}</p>
                    </div>
                  )}
                  {detail.conversation.status === "human_takeover_requested"
                    || detail.conversation.status === "human_takeover_active" ? (
                    <form
                      className="flex flex-col gap-2"
                      onSubmit={(event) => {
                        event.preventDefault();
                        if (!token || !businessId || !selectedId || !riskDraft.trim() || riskBusy) return;
                        setRiskBusy(true);
                        setRiskError(null);
                        api
                          .replyToConversation(token, businessId, selectedId, riskDraft.trim())
                          .then(() => {
                            setRiskDraft("");
                            return Promise.all([
                              refreshDetail(selectedId),
                              api.listConversations(token, businessId).then((res) => setConversations(res.conversations)),
                            ]);
                          })
                          .catch((err) => setRiskError(describeError(err)))
                          .finally(() => setRiskBusy(false));
                      }}
                    >
                      <p className="text-sm text-mute">
                        Risk or policy only — this is not a sales close. The engine still owns a normal sale.
                      </p>
                      {riskError && (
                        <p className="text-xs" style={{ color: "#8A3225" }}>{riskError}</p>
                      )}
                      <textarea
                        aria-label="Risk reply"
                        value={riskDraft}
                        onChange={(event) => setRiskDraft(event.target.value)}
                        rows={3}
                        className="w-full rounded-lg border border-line px-3 py-2 text-sm outline-none"
                        placeholder="Write a policy or emergency reply…"
                      />
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="submit"
                          disabled={riskBusy || !riskDraft.trim()}
                          className="text-sm font-medium px-4 py-2 rounded-lg text-[#0B0B0D] disabled:opacity-50"
                          style={{ backgroundColor: "#C6FF00" }}
                        >
                          {riskBusy ? "Sending…" : "Send risk reply"}
                        </button>
                        {caseDetail?.current_state === "NEEDS_HUMAN" && (
                          <button
                            type="button"
                            disabled={riskBusy}
                            onClick={() => {
                              if (!token || !businessId || !selectedId) return;
                              setRiskBusy(true);
                              setRiskError(null);
                              api
                                .resolveConversation(token, businessId, selectedId)
                                .then(() => Promise.all([
                                  refreshDetail(selectedId),
                                  api.listConversations(token, businessId).then((res) => setConversations(res.conversations)),
                                ]))
                                .catch((err) => setRiskError(describeError(err)))
                                .finally(() => setRiskBusy(false));
                            }}
                            className="text-sm font-medium px-4 py-2 rounded-lg border border-line"
                          >
                            Resolve
                          </button>
                        )}
                      </div>
                    </form>
                  ) : (
                    <p className="text-sm text-mute">
                      Watch only. The engine talks until Done. Open the board and click a lead to read the thread there too.
                    </p>
                  )}
                </div>
              </>
            )}
          </div>

          <div className="w-80 shrink-0 border-l border-line p-5 hidden lg:flex flex-col gap-6">
            {stateInfo && (
              <div>
                <div className="text-xs font-medium text-clay mb-2">Case status</div>
                <p className="text-[11px] text-clay mb-2 leading-relaxed">
                  Process state for this deal — not the sales conversation stage.
                </p>
                <Stepper stage={stateInfo.stage} color="#FF5A36" labels />
              </div>
            )}
            <div className="flex items-center gap-4 text-xs text-mute">
              <span className="flex items-center gap-1.5"><Phone size={12} /> {caseDetail?.lead.phone || "Not on file"}</span>
              <span className="flex items-center gap-1.5"><Mail size={12} /> {caseDetail?.lead.email || "Not on file"}</span>
            </div>
            <div>
              <div className="text-xs font-medium text-clay mb-3" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
                {caseDetail ? `${caseDetail.case_id.slice(0, 8)} · audit trail` : "audit trail"}
              </div>
              {!caseDetail ? (
                <p className="text-xs text-clay">This conversation isn't linked to a case yet.</p>
              ) : (
                <div className="flex flex-col gap-2.5 text-sm">
                  {caseDetail.events.map((e) => {
                    const meta = describeEvent(e.event_type);
                    return (
                      <div key={e.event_id} className="flex gap-3">
                        <span className="text-clay shrink-0" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12 }}>
                          {new Date(e.occurred_at).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                        </span>
                        <span className="font-medium shrink-0 w-16">{meta.stage}</span>
                        <span className="text-mute">{meta.label}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
