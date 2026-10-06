import { useEffect, useMemo, useState } from "react";
import { CRM_BOARD_TABS, CRM_TAB_META } from "../lib/crmBoard";
import { brand } from "./theme";
import {
  BOARD_PREVIEW_CAPTION,
  BOARD_PREVIEW_DEFAULT_TAB,
  BOARD_PREVIEW_HOLD_MS,
  BOARD_PREVIEW_SCENES,
  boardPreviewCounts,
  boardPreviewPerson,
  nextBoardPreviewTab,
  type BoardPreviewTab,
} from "./boardPreview";

const MONO = "'IBM Plex Mono', ui-monospace, monospace";

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return reduced;
}

export function BoardPreview() {
  const reducedMotion = usePrefersReducedMotion();
  const [tab, setTab] = useState<BoardPreviewTab>(BOARD_PREVIEW_DEFAULT_TAB);
  const [selectedId, setSelectedId] = useState(BOARD_PREVIEW_SCENES[BOARD_PREVIEW_DEFAULT_TAB].people[0].id);
  const [userPaused, setUserPaused] = useState(false);
  const [hoverPaused, setHoverPaused] = useState(false);
  const [visibleCount, setVisibleCount] = useState(0);
  const counts = useMemo(() => boardPreviewCounts(), []);
  const scene = BOARD_PREVIEW_SCENES[tab];
  const selected = boardPreviewPerson(scene, selectedId);
  const emptyThread = selected.messages.length === 0;
  const paused = reducedMotion || userPaused || hoverPaused;
  const shownMessages = reducedMotion ? selected.messages : selected.messages.slice(0, visibleCount);

  const openTab = (next: BoardPreviewTab, fromUser = false) => {
    if (fromUser) setUserPaused(true);
    setTab(next);
    setSelectedId(BOARD_PREVIEW_SCENES[next].people[0].id);
  };

  const openPerson = (personId: string) => {
    setUserPaused(true);
    setSelectedId(personId);
  };

  useEffect(() => {
    setVisibleCount(reducedMotion ? selected.messages.length : 0);
  }, [selected.id, tab, reducedMotion, selected.messages.length]);

  useEffect(() => {
    if (reducedMotion || visibleCount >= selected.messages.length) return;
    const timer = window.setTimeout(
      () => setVisibleCount((count) => count + 1),
      visibleCount === 0 ? 80 : 620,
    );
    return () => window.clearTimeout(timer);
  }, [visibleCount, selected.messages.length, selected.id, reducedMotion]);

  useEffect(() => {
    if (paused) return;
    const timer = window.setTimeout(() => {
      const next = nextBoardPreviewTab(tab);
      setTab(next);
      setSelectedId(BOARD_PREVIEW_SCENES[next].people[0].id);
    }, BOARD_PREVIEW_HOLD_MS[tab]);
    return () => window.clearTimeout(timer);
  }, [tab, paused]);

  return (
    <figure
      className="relative m-0 min-w-0 pt-2 pr-3 pb-4"
      aria-label="Architecture preview of the live CRM board"
      onMouseEnter={() => setHoverPaused(true)}
      onMouseLeave={() => setHoverPaused(false)}
    >
      <div
        aria-hidden="true"
        className="absolute left-2 right-0 top-0 bottom-2 -rotate-2"
        style={{ background: brand.lime }}
      />
      <div
        className="relative overflow-hidden"
        style={{
          background: brand.panel,
          border: `1px solid ${brand.ink}`,
          boxShadow: `8px 8px 0 ${brand.ink}`,
        }}
      >
        <div
          className="flex items-center justify-between gap-3 px-4 py-2.5"
          style={{ background: brand.ink, color: brand.cream }}
        >
          <span className="inline-flex items-center gap-2 text-[11px] font-semibold tracking-[0.04em]">
            <span
              className="inline-block h-1.5 w-1.5 rounded-full shrink-0 motion-safe:animate-pulse"
              style={{ background: brand.lime, boxShadow: "0 0 0 3px rgba(198,255,0,0.16)" }}
              aria-hidden="true"
            />
            Client 0 board
          </span>
          <span className="text-[10px] uppercase tracking-[0.16em]" style={{ color: "#D9D0C2", fontFamily: MONO }}>
            Architecture preview
          </span>
        </div>

        <div className="grid grid-cols-4" style={{ borderBottom: `1px solid ${brand.line}` }}>
          {CRM_BOARD_TABS.map((item) => {
            const active = item === tab;
            return (
              <button
                key={item}
                type="button"
                onClick={() => openTab(item, true)}
                className="px-1 sm:px-2 py-2.5 text-center text-[10px] sm:text-[11px] leading-tight font-medium"
                style={{
                  backgroundColor: active ? brand.coralWash : "transparent",
                  color: active ? brand.coral : brand.mute,
                  boxShadow: active ? `inset 0 -2px 0 ${brand.coral}` : undefined,
                }}
                aria-pressed={active}
              >
                <span className="block">{CRM_TAB_META[item].label}</span>
                <span className="block mt-0.5" style={{ fontFamily: MONO, opacity: 0.85 }}>
                  {counts[item]}
                </span>
              </button>
            );
          })}
        </div>
        <p
          className="px-4 py-2 text-[11px] text-mute flex items-center justify-between gap-3"
          style={{ borderBottom: `1px solid ${brand.line}` }}
        >
          <span>{CRM_TAB_META[tab].hint}</span>
          {tab === "in_progress" && (
            <span
              className="inline-flex items-center gap-1.5 shrink-0 text-[10px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: brand.limeInk, fontFamily: MONO }}
            >
              <span
                className="inline-block h-1.5 w-1.5 rounded-full motion-safe:animate-pulse"
                style={{ background: brand.lime }}
                aria-hidden="true"
              />
              Live
            </span>
          )}
        </p>

        <div className="grid sm:grid-cols-[minmax(0,0.9fr)_minmax(0,1.2fr)] items-stretch min-h-[280px]">
          <ul className="min-w-0 flex flex-col sm:border-r" style={{ borderColor: brand.line }}>
            {scene.people.map((person) => {
              const active = person.id === selected.id;
              return (
                <li key={person.id} className="border-b" style={{ borderColor: brand.line }}>
                  <button
                    type="button"
                    onClick={() => openPerson(person.id)}
                    className="w-full text-left px-4 py-3"
                    style={{
                      backgroundColor: active ? brand.coralWash : "transparent",
                      boxShadow: active ? `inset 3px 0 0 ${brand.coral}` : undefined,
                    }}
                    aria-pressed={active}
                  >
                    <span className="flex items-start justify-between gap-3">
                      <span className="min-w-0">
                        <span className="block text-sm font-semibold truncate">{person.name}</span>
                        <span className="block text-[12px] text-mute mt-0.5 leading-snug">{person.summary}</span>
                      </span>
                      <span className="text-[10px] text-clay shrink-0 mt-0.5" style={{ fontFamily: MONO }}>
                        {person.when}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
            <li className="flex-1 px-4 py-3 text-[11px] text-clay leading-relaxed">
              Watch only. You do not hop in to close.
            </li>
          </ul>

          <div className="min-w-0 px-4 py-3 flex flex-col gap-2.5" style={{ background: "#FFFCF6" }}>
            <div>
              <div className="text-sm font-semibold">{selected.name}</div>
              <div className="text-[11px] text-mute mt-0.5">{CRM_TAB_META[tab].label} · watch only</div>
            </div>
            {emptyThread ? (
              <p className="text-[12px] text-mute leading-relaxed py-2">
                No conversation yet. The engine has not written.
              </p>
            ) : (
              <div className="flex flex-col gap-2.5">
                {shownMessages.map((message) => {
                  const inbound = message.from === "person";
                  return (
                    <div
                      key={message.text}
                      className={`ev-board-msg flex flex-col ${inbound ? "items-start" : "items-end"}`}
                    >
                      <p
                        className="text-[12px] leading-relaxed max-w-[94%] px-3 py-2 rounded-2xl"
                        style={{
                          backgroundColor: inbound ? "#F1F1EF" : "#FFE4D6",
                          color: brand.ink,
                        }}
                      >
                        {message.text}
                      </p>
                      <span className="text-[10px] text-clay mt-1" style={{ fontFamily: MONO }}>
                        {inbound ? selected.name : "Engine"}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
      <figcaption className="relative mt-3 text-[11px] text-clay tracking-[0.04em]">
        {BOARD_PREVIEW_CAPTION}. The step and the dialogue, as they happen.
      </figcaption>
    </figure>
  );
}
