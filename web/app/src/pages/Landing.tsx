import { Suspense, lazy, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Check, ShieldCheck } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { FaqSection } from "../components/FaqSection";
import { MarketingFooter, MarketingHeader } from "../brand/MarketingChrome";
import { brand } from "../brand/theme";

const OrbitScene = lazy(() => import("../brand/OrbitScene").then((mod) => ({ default: mod.OrbitScene })));

function useDesktopHero() {
  const [desktop, setDesktop] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia("(min-width: 768px)").matches : true,
  );
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const update = () => setDesktop(mq.matches);
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return desktop;
}

function Block({ n, title, body, tone }: { n: string; title: string; body: string; tone: "ink" | "coral" | "lime" }) {
  const bg = tone === "ink" ? brand.ink : tone === "coral" ? brand.coral : brand.lime;
  const fg = tone === "lime" ? brand.ink : brand.cream;
  return (
    <div className="p-6 min-h-[160px] flex flex-col justify-between" style={{ background: bg, color: fg }}>
      <div className="ev-display text-4xl">{n} {title}</div>
      <p className="text-sm leading-relaxed mt-6 max-w-xs">{body}</p>
    </div>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const desktopHero = useDesktopHero();
  const primaryCtaTarget = user ? (user.business_ids.length > 0 ? "/app" : "/onboarding") : "/signup";

  return (
    <div className="ev-page min-h-screen w-full overflow-x-hidden">
      <MarketingHeader />

      <section className="relative min-h-[92vh] max-w-6xl mx-auto px-6 pt-10 md:pt-16 pb-10">
        {desktopHero ? (
          <div className="absolute inset-y-0 right-[-8%] w-[58%] pointer-events-none ev-orbit-frame ev-orbit-hero" aria-hidden="true">
            <Suspense fallback={null}>
              <OrbitScene variant="hero" />
            </Suspense>
          </div>
        ) : null}
        <div className="relative z-10 max-w-xl">
          <div className="inline-block mb-5 text-[11px] font-extrabold uppercase tracking-[0.16em] px-3 py-1.5 -rotate-2" style={{ background: "#C6FF00", color: "#0B0B0D" }}>
            Ready-made sales cycle · not a CRM
          </div>
          <h1 className="ev-display text-[72px] md:text-[112px] text-ink">
            FROM INQUIRY<br />TO A DEAL.
          </h1>
          {!desktopHero ? (
            <div className="relative h-[250px] w-[250px] max-w-full mx-auto my-6 ev-orbit-frame ev-orbit-mobile" aria-hidden="true">
              <img
                src="/brand/evorove-still-torus-square.png"
                alt=""
                draggable={false}
                className="w-full h-full object-contain select-none pointer-events-none"
              />
            </div>
          ) : null}
          <p className="text-base md:text-lg text-mute leading-relaxed mt-6 mb-8 max-w-md">
            Evorove is an automated sales process. A trained AI agent takes the inquiry you already have,
            qualifies it, handles objections, follows up, and closes — without you writing prompts or
            updating a pipeline.
          </p>
          <div className="flex flex-wrap items-center gap-3 mb-12">
            <button
              onClick={() => navigate(primaryCtaTarget)}
              className="text-[12px] font-bold uppercase tracking-[0.14em] px-5 py-3 rounded-full inline-flex items-center gap-2"
              style={{ background: "#C6FF00", color: "#0B0B0D" }}
            >
              Start free trial <ArrowRight size={15} />
            </button>
            <a href="#how" className="text-[12px] font-bold uppercase tracking-[0.14em] px-5 py-3 rounded-full" style={{ background: "#0B0B0D", color: "#F7F1E4" }}>
              See the cycle
            </a>
          </div>
          <div className="flex gap-10">
            <div>
              <div className="ev-display text-5xl">24/7</div>
              <div className="text-xs uppercase tracking-[0.16em] text-clay">The sale keeps moving</div>
            </div>
            <div>
              <div className="ev-display text-5xl">$199</div>
              <div className="text-xs uppercase tracking-[0.16em] text-clay">Instead of a hire</div>
            </div>
            <div>
              <div className="ev-display text-5xl">0</div>
              <div className="text-xs uppercase tracking-[0.16em] text-clay">Prompts to write</div>
            </div>
          </div>
        </div>
      </section>

      <section id="how" className="max-w-6xl mx-auto px-6 pb-6">
        <div className="grid md:grid-cols-3 gap-2.5">
          <Block n="01" title="RECEIVE" tone="ink" body="Same-minute answer on web chat or text. The inquiry you already paid for does not go quiet." />
          <Block n="02" title="SELL" tone="coral" body="Qualifies, answers objections, and keeps the conversation moving. You do not prompt it." />
          <Block n="03" title="CLOSE" tone="lime" body="Books, quotes, or hands you a prepared deal. Follow-up runs until there is an outcome." />
        </div>
      </section>

      <section id="features" className="max-w-6xl mx-auto px-6 py-20 md:py-28">
        <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-coral mb-3">How it sells</p>
        <h2 className="ev-display text-6xl md:text-7xl mb-10">A ready-made sales process.<br />Not a board you update.</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            ["Not a CRM", "A CRM stores the pipeline. Evorove runs the sale: it talks to the lead, follows up, and works toward a booked or quoted deal."],
            ["Not a chatbot you prompt", "The agent is already trained to conduct a sale. You describe the business once. There is no prompt to maintain."],
            ["Leads stop leaking", "Nights, weekends, half-finished chats — the cycle continues until there is a next step or a handoff."],
            ["Costs less than a person on the line", "$199 a month instead of a full-time hire sitting on the same inquiries you already paid to get."],
          ].map(([title, body]) => (
            <div key={title} className="p-6 border" style={{ borderColor: "#E4DCCB", background: "#FFFCF6" }}>
              <h3 className="font-semibold mb-2">{title}</h3>
              <p className="text-sm text-mute leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="trust" className="border-y" style={{ borderColor: "#E4DCCB", background: "#0B0B0D", color: "#F7F1E4" }}>
        <div className="max-w-6xl mx-auto px-6 py-20 md:py-24 grid md:grid-cols-2 gap-12 items-center">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.22em] mb-3" style={{ color: "#C6FF00" }}>The sale, logged</p>
            <h2 className="ev-display text-6xl mb-6">Every move toward the deal is visible.</h2>
            <ul className="flex flex-col gap-3.5">
              {[
                "The agent phrases the sale. It cannot invent a price, a discount, or a promise",
                "Objections, follow-ups, and the next commitment stay inside the process",
                "You can trace a booking or a quote back to the exact step",
              ].map((t) => (
                <li key={t} className="flex items-start gap-2.5 text-sm">
                  <Check size={16} className="mt-0.5 shrink-0" color="#C6FF00" /> {t}
                </li>
              ))}
            </ul>
          </div>
          <div className="p-5" style={{ background: "#161616", border: "1px solid #2A2A2A" }}>
            <div className="text-xs mb-3" style={{ fontFamily: "'IBM Plex Mono', monospace", color: "#9A8F83" }}>CS-1042 · sales cycle</div>
            <div className="flex flex-col gap-2.5 text-sm">
              {[
                ["09:41:02", "Receive", "Inbound web chat — existing inquiry"],
                ["09:41:04", "Sell", "Need and timeline confirmed"],
                ["09:42:11", "Sell", "Price objection answered from facts"],
                ["09:44:18", "Follow-up", "Next-step reminder scheduled"],
                ["09:51:02", "Close", "Consultation booked"],
              ].map(([time, stage, desc]) => (
                <div key={`${time}-${stage}`} className="flex gap-3">
                  <span className="shrink-0" style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, color: "#9A8F83" }}>{time}</span>
                  <span className="font-medium shrink-0 w-16" style={{ color: "#C6FF00" }}>{stage}</span>
                  <span className="text-[#C9C2B6]">{desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <FaqSection />

      <section className="max-w-6xl mx-auto px-6 py-20 md:py-28 text-center">
        <h2 className="ev-display text-6xl md:text-7xl mb-5">Your next inquiry<br />is already deciding.</h2>
        <p className="text-mute mb-8 max-w-md mx-auto">Ready-made sales process. Seven-day trial. No prompt engineering. $199/mo after trial.</p>
        <button
          onClick={() => navigate(primaryCtaTarget)}
          className="text-[12px] font-bold uppercase tracking-[0.14em] px-6 py-3.5 rounded-full inline-flex items-center gap-2"
          style={{ background: "#FF5A36", color: "#0B0B0D" }}
        >
          Run it on your next lead <ArrowRight size={15} />
        </button>
      </section>

      <div className="max-w-6xl mx-auto px-6 pb-8 flex items-center justify-center gap-2 text-sm text-clay">
        <ShieldCheck size={15} /> The agent can phrase the sale — never a price, a discount, or a promise you did not approve.
      </div>

      <MarketingFooter />
    </div>
  );
}
