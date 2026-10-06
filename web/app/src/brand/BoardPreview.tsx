import { useMemo, useState } from "react";
import { CRM_BOARD_TABS, CRM_TAB_META } from "../lib/crmBoard";
import { brand } from "./theme";
import {
  BOARD_PREVIEW_CAPTION,
  BOARD_PREVIEW_DEFAULT_TAB,
  BOARD_PREVIEW_SCENES,
  boardPreviewCounts,
  boardPreviewPerson,
  type BoardPreviewTab,
} from "./boardPreview";

export function BoardPreview() {
  const [tab, setTab] = useState<BoardPreviewTab>(BOARD_PREVIEW_DEFAULT_TAB);
  const [selectedId, setSelectedId] = useState(BOARD_PREVIEW_SCENES[BOARD_PREVIEW_DEFAULT_TAB].people[0].id);
  const counts = useMemo(() => boardPreviewCounts(), []);
  const scene = BOARD_PREVIEW_SCENES[tab];
  const selected = boardPreviewPerson(scene, selectedId);
  const emptyThread = selected.messages.length === 0;

  const openTab = (next: BoardPreviewTab) => {
    setTab(next);
    setSelectedId(BOARD_PREVIEW_SCENES[next].people[0].id);
  };

  return (
    <figure className="relative m-0 min-w-0 pr-2 pb-2" aria-label="Architecture preview of the live CRM board">
      <div
        className="overflow-hidden"
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
          <span className="text-[10px] uppercase tracking-[0.16em]" style={{ color: "#D9D0C2" }}>
            Architecture preview
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 px-4 py-3" style={{ borderBottom: `1px solid ${brand.line}` }}>
          {CRM_BOARD_TABS.map((item) => {
            const active = item === tab;
            return (
              <button
                key={item}
                type="button"
                onClick={() => openTab(item)}
                className="px-2.5 py-1 rounded-full text-[11px] font-medium whitespace-nowrap"
                style={{
                  backgroundColor: active ? brand.coralWash : "transparent",
                  color: active ? brand.coral : brand.mute,
                }}
                aria-pressed={active}
              >
                {CRM_TAB_META[item].label} ({counts[item]})
              </button>
            );
          })}
        </div>
        <p className="px-4 py-2 text-[11px] text-mute" style={{ borderBottom: `1px solid ${brand.line}` }}>
          {CRM_TAB_META[tab].hint}
        </p>

        <div className="grid sm:grid-cols-[minmax(0,0.92fr)_minmax(0,1.15fr)]">
          <ul className="min-w-0 sm:border-r" style={{ borderColor: brand.line }}>
            {scene.people.map((person) => {
              const active = person.id === selected.id;
              return (
                <li key={person.id} className="border-b" style={{ borderColor: brand.line }}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(person.id)}
                    className="w-full text-left px-4 py-3"
                    style={{ backgroundColor: active ? brand.coralWash : "transparent" }}
                    aria-pressed={active}
                  >
                    <span className="flex items-start justify-between gap-3">
                      <span className="min-w-0">
                        <span className="block text-sm font-semibold truncate">{person.name}</span>
                        <span className="block text-[12px] text-mute mt-0.5 leading-snug">{person.summary}</span>
                      </span>
                      <span className="text-[10px] text-clay shrink-0 mt-0.5">{person.when}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          <div className="min-w-0 min-h-[220px] px-4 py-3 flex flex-col gap-2.5" style={{ background: "#FFFCF6" }}>
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
                {selected.messages.map((message) => {
                  const inbound = message.from === "person";
                  return (
                    <div key={message.text} className={`flex flex-col ${inbound ? "items-start" : "items-end"}`}>
                      <p
                        className="text-[12px] leading-relaxed max-w-[92%] px-3 py-2"
                        style={{
                          backgroundColor: inbound ? "#F1F1EF" : "#FFE4D6",
                          color: brand.ink,
                        }}
                      >
                        {message.text}
                      </p>
                      <span className="text-[10px] text-clay mt-1">
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
      <figcaption className="mt-3 text-[11px] text-clay tracking-[0.04em]">
        {BOARD_PREVIEW_CAPTION}. The step and the dialogue, as they happen.
      </figcaption>
    </figure>
  );
}
