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
          <div className="absolute top-[46%] right-0 -translate-y-1/2 w-[min(46%,540px)] aspect-square pointer-events-none ev-orbit-frame ev-orbit-desktop" aria-hidden="true">
            <Suspense fallback={null}>
              <OrbitScene variant="hero" />
            </Suspense>
          </div>
        ) : null}
        <div className="relative z-10 max-w-xl">
          <div className="inline-block mb-5 text-[11px] font-extrabold uppercase tracking-[0.16em] px-3 py-1.5 -rotate-2" style={{ background: "#C6FF00", color: "#0B0B0D" }}>
            Find · sell · close
          </div>
          <h1 className="ev-display text-[72px] md:text-[112px] text-ink">
            COLD IN.<br />DONE ON THE BOARD.
          </h1>
          {!desktopHero ? (
            <div className="relative h-[280px] w-[280px] max-w-full mx-auto my-6 ev-orbit-frame ev-orbit-mobile" aria-hidden="true">
              <Suspense fallback={null}>
                <OrbitScene variant="hero" />
              </Suspense>
            </div>
          ) : null}
          <p className="text-base md:text-lg text-mute leading-relaxed mt-6 mb-8 max-w-md">
            Subscribe. Tell Evorove the business. It studies your setup, finds people in the open web,
            puts them on Cold, then sells until the deal is done — a booked hour, or money in your account.
            You watch the board. You do not hop in to close.
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
              See how it works
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
              <div className="ev-display text-5xl">4</div>
              <div className="text-xs uppercase tracking-[0.16em] text-clay">CRM tabs, evening view</div>
            </div>
          </div>
        </div>
      </section>

      <section id="how" className="max-w-6xl mx-auto px-6 pb-6">
        <div className="grid md:grid-cols-3 gap-2.5">
          <Block n="01" title="FIND" tone="ink" body="After you describe the business: what you sell, who it's for, how you reach them. Then it finds your audience in public places. Fit the profile — then Cold. Not your website form." />
          <Block n="02" title="SELL" tone="coral" body="It writes first. A model trained on sales books works objections, names value, sends your offer when they are ready. You do not prompt it. You do not hop on to close." />
          <Block n="03" title="DONE" tone="lime" body="Offline: a real hour for the service you sell. Online: they buy, money hits your account. CRM moves them to Done." />
        </div>
      </section>

      <section id="features" className="max-w-6xl mx-auto px-6 py-20 md:py-28">
        <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-coral mb-3">How it fits together</p>
        <h2 className="ev-display text-6xl md:text-7xl mb-10">Subscribe.<br />Then the board fills itself.</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {[
            ["You connect once", "Pay the subscription. Fill in the business, multimedia, and the commercial offer if you have one. That's the setup — not a list of leads."],
            ["Then it thinks, then it hunts", "It studies your offer, looks at public data, and checks each person twice against what you described. Only then does a person land in Cold."],
            ["Then it sells", "Each Cold lead gets a live conversation. Objections, techniques, your offer at the right moment. The engine talks until Done."],
            ["The board moves as it happens", "Cold, In progress, Offer made, Done — each step shows up when it happens. Open a person and the dialogue is there. Do not jump in to close a normal sale."],
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
            <p className="text-[11px] font-bold uppercase tracking-[0.22em] mb-3" style={{ color: "#C6FF00" }}>The board, logged</p>
            <h2 className="ev-display text-6xl mb-6">Every move toward Done is visible.</h2>
            <ul className="flex flex-col gap-3.5">
              {[
                "The agent phrases the sale. It cannot invent a price, a discount, or a promise",
                "Cold is people found in the open field — not visitors who already filled your form",
                "You can open a thread and watch. Closing stays with the engine",
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
                ["09:41:02", "Find", "Public match — reason on file — Cold"],
                ["09:41:04", "Sell", "First outbound. Engine, not staff"],
                ["09:42:11", "Sell", "Price objection answered from facts"],
                ["09:51:02", "Done", "Paid, or the hour is set"],
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
        <h2 className="ev-display text-6xl md:text-7xl mb-5">Open the board.<br />The cold ones are already there.</h2>
        <p className="text-mute mb-8 max-w-md mx-auto">Seven-day trial. No prompt engineering. $199/mo after trial.</p>
        <button
          onClick={() => navigate(primaryCtaTarget)}
          className="text-[12px] font-bold uppercase tracking-[0.14em] px-6 py-3.5 rounded-full inline-flex items-center gap-2"
          style={{ background: "#FF5A36", color: "#0B0B0D" }}
        >
          Run the sale <ArrowRight size={15} />
        </button>
      </section>

      <div className="max-w-6xl mx-auto px-6 pb-8 flex items-center justify-center gap-2 text-sm text-clay">
        <ShieldCheck size={15} /> The agent can phrase the sale — never a price, a discount, or a promise you did not approve.
      </div>

      <MarketingFooter />
    </div>
  );
}
