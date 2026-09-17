import { useNavigate } from "react-router-dom";
import {
  ArrowRight, ShieldCheck, Check, Scale,
  CalendarCheck, UserCheck, FileWarning, Clock,
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { MarketingFooter, MarketingHeader } from "../brand/MarketingChrome";

/**
 * Wave 1 door for solo & small family-law / general-practice attorneys
 * (CA & NY first). Same three-cycle product as `/` — not an inbound intake
 * tool, not a lawyer-only engine. Outreach can still land here.
 */

function StatChip({ n, label }: { n: string; label: string }) {
  return (
    <div className="bg-white rounded-xl border border-line p-4">
      <div className="ev-display text-3xl mb-1" style={{ color: "#FF5A36" }}>
        {n}
      </div>
      <div className="text-xs text-mute leading-snug">{label}</div>
    </div>
  );
}

function DoesItem({ text }: { text: string }) {
  return (
    <li className="flex items-start gap-2.5 text-sm text-ink">
      <Check size={16} className="mt-0.5 shrink-0" color="#1E7B52" /> {text}
    </li>
  );
}

function FaqItem({ q, a }: { q: string; a: string }) {
  return (
    <div className="py-5 border-b border-line last:border-0">
      <div className="text-sm font-semibold mb-1.5">{q}</div>
      <div className="text-sm text-mute leading-relaxed">{a}</div>
    </div>
  );
}

export default function LawyersLanding() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const primaryCtaTarget = user ? (user.business_ids.length > 0 ? "/app" : "/onboarding") : "/signup";

  return (
    <div className="ev-page min-h-screen w-full">
      <MarketingHeader
        homeTo="/lawyers"
        ctaLabel="Start free trial"
        links={[
          { href: "#cycle", label: "The cycle" },
          { href: "#pricing", label: "Pricing" },
          { href: "#faq", label: "FAQ" },
        ]}
      />

      <section className="max-w-4xl mx-auto px-6 pt-16 md:pt-24 pb-14 text-center">
        <div className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full mb-6" style={{ backgroundColor: "#FFE8E1", color: "#FF5A36" }}>
          <Scale size={12} /> Solo & small practices — CA &amp; NY first. Same engine as any service business.
        </div>
        <h1 className="ev-display text-6xl md:text-7xl leading-[0.9] mb-5">
          Cold on the board.<br />Consult already sold.
        </h1>
        <p className="text-base md:text-lg text-mute leading-relaxed mb-8 max-w-2xl mx-auto">
          Subscribe. Describe the practice. Evorove studies the packet, finds people in the open web,
          puts them on Cold, then sells until Done — a booked consult hour. The board moves as it happens. Open a person to read the dialogue.
          You do not hop in to close. Hard limits: no legal advice, no promised outcome.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <button
            onClick={() => navigate(primaryCtaTarget)}
            className="text-sm font-bold uppercase tracking-wide px-5 py-3 rounded-full flex items-center gap-2"
            style={{ backgroundColor: "#C6FF00", color: "#0B0B0D" }}
          >
            Start your 7-day free trial <ArrowRight size={15} />
          </button>
          <a href="#cycle" className="text-sm font-medium px-5 py-3 rounded-full border border-ink">
            See the cycle
          </a>
        </div>
        <span className="block text-xs text-clay mt-4">$199/mo after trial · card required, no charge until trial ends</span>
      </section>

      <section className="border-y border-line bg-white">
        <div className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-center gap-3 text-sm text-clay text-center">
          <ShieldCheck size={15} className="shrink-0" /> Discloses itself as AI, every time — built for the standard California (SB 243) and New York (Article 47) already require.
        </div>
      </section>

      <section id="cycle" className="max-w-4xl mx-auto px-6 py-16 md:py-20">
        <span className="text-xs font-medium uppercase tracking-wide" style={{ color: "#FF5A36" }}>Find · sell · close</span>
        <h2 className="ev-display text-4xl md:text-5xl mt-2 mb-5">
          Law is a door. The product is the three cycles.
        </h2>
        <p className="text-base text-mute leading-relaxed max-w-2xl mb-8">
          A consult hour still costs real marketing money if you only wait for people who already
          found the site. Cycle 1 looks in the open field. Cycle 2 writes first. Done is the hour
          on the calendar — CRM, not a voicemail you return.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatChip n="Cold" label="Found in public, not written yet" />
          <StatChip n="In progress" label="The engine is in the conversation" />
          <StatChip n="Offer made" label="Value named. Not closed." />
          <StatChip n="Done" label="The consult hour is set" />
        </div>
      </section>

      <section id="different" className="bg-white border-y border-line">
        <div className="max-w-4xl mx-auto px-6 py-16 md:py-20">
          <span className="text-xs font-medium uppercase tracking-wide" style={{ color: "#FF5A36" }}>How Evorove is different</span>
          <h2 className="ev-display text-4xl md:text-5xl mt-2 mb-6">
            A trained sales process, not a chatbot you prompt.
          </h2>
          <p className="text-base text-mute leading-relaxed mb-6 max-w-2xl">
            Most tools sold to firms stop at capture: they take a name and drop the rest on you.
            Evorove finds, then runs the sale — qualification, objections, the offer when they are
            ready — until the consult is booked. No prompts. You watch the thread. You do not close it.
          </p>
          <p className="text-base text-mute leading-relaxed mb-8 max-w-2xl">
            That is safe to put in front of a client because the AI never decides the law.
            It only phrases a move the process already chose. Case qualification, escalation, and what
            the agent is not allowed to say live in the engine, not in a prompt it could talk itself out of.
          </p>
          <div className="grid sm:grid-cols-2 gap-4 mb-8">
            <div className="rounded-xl border border-line bg-cream p-6">
              <div className="text-xs font-semibold uppercase tracking-wide text-mute mb-4">Intake chatbot on a prompt</div>
              <ul className="flex flex-col gap-3 text-sm text-mute">
                <li className="pt-3 border-t border-line first:pt-0 first:border-0">Waits for someone who already wrote in</li>
                <li className="pt-3 border-t border-line">The AI decides what to say, guided by instructions</li>
                <li className="pt-3 border-t border-line">Can be talked into estimating a case or promising an outcome</li>
                <li className="pt-3 border-t border-line">You still have to sell and book</li>
              </ul>
            </div>
            <div className="rounded-xl p-6" style={{ backgroundColor: "#0B0B0D" }}>
              <div className="text-xs font-semibold uppercase tracking-wide mb-4" style={{ color: "#C6FF00" }}>Evorove</div>
              <ul className="flex flex-col gap-3 text-sm" style={{ color: "#E7E2D5" }}>
                <li className="pt-3 border-t first:pt-0 first:border-0" style={{ borderColor: "#33302B" }}>Finds in the open web, then writes first from Cold</li>
                <li className="pt-3 border-t" style={{ borderColor: "#33302B" }}>Runs the sale until they are ready to book — you do not prompt it</li>
                <li className="pt-3 border-t" style={{ borderColor: "#33302B" }}>Has no path to invent legal analysis or promise a result</li>
                <li className="pt-3 border-t" style={{ borderColor: "#33302B" }}>Identifies itself as AI from the first message, every time</li>
              </ul>
            </div>
          </div>
          <div className="grid sm:grid-cols-3 gap-4">
            <div className="rounded-xl border border-line p-5">
              <FileWarning size={18} color="#FF5A36" className="mb-3" />
              <div className="text-sm font-semibold mb-1">Can't estimate outcomes</div>
              <div className="text-xs text-mute leading-relaxed">No path in the message pipeline to invent legal analysis or promise a result.</div>
            </div>
            <div className="rounded-xl border border-line p-5">
              <UserCheck size={18} color="#FF5A36" className="mb-3" />
              <div className="text-sm font-semibold mb-1">Always identifies as AI</div>
              <div className="text-xs text-mute leading-relaxed">A visible disclosure badge stays on screen for the whole conversation, not buried in a footer.</div>
            </div>
            <div className="rounded-xl border border-line p-5">
              <Clock size={18} color="#FF5A36" className="mb-3" />
              <div className="text-sm font-semibold mb-1">Same limits, every plan</div>
              <div className="text-xs text-mute leading-relaxed">The compliance architecture isn't a premium feature — it's how every message gets built, always.</div>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-4xl mx-auto px-6 py-16 md:py-20">
        <span className="text-xs font-medium uppercase tracking-wide" style={{ color: "#FF5A36" }}>What it does</span>
        <h2 className="ev-display text-4xl md:text-5xl mt-2 mb-7">
          The sale runs until they are ready to book.
        </h2>
        <ul className="flex flex-col gap-3.5 max-w-lg">
          <DoesItem text="Studies your packet — practice, materials, commercial offer — before it hunts" />
          <DoesItem text="Places matching people on Cold, then writes first. A website chat is only a channel, never the source of Cold" />
          <DoesItem text="Handles cost and fit objections from facts you approved, then sends the offer when they are ready" />
          <DoesItem text="Closes to a real consult hour on Done. You watch. You do not hop in to close a normal sale" />
          <DoesItem text="Never estimates case outcomes, gives legal advice, or promises a result — by design, not by request" />
        </ul>
      </section>

      <section className="bg-white border-y border-line">
        <div className="max-w-4xl mx-auto px-6 py-14 md:py-16 flex flex-col md:flex-row items-start md:items-center gap-6 justify-between">
          <div>
            <h2 className="ev-display text-3xl mb-2">Built for solo practices</h2>
            <p className="text-sm text-mute leading-relaxed max-w-lg">
              Evorove Starter is built for exactly one attorney, one jurisdiction — describe the
              practice once, no developer or prompt engineering.
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm font-medium shrink-0 px-4 py-2.5 rounded-lg" style={{ backgroundColor: "#FFE8E1", color: "#FF5A36" }}>
            <CalendarCheck size={16} /> ~20 minutes to go live
          </div>
        </div>
      </section>

      <section id="pricing" className="max-w-2xl mx-auto px-6 py-16 md:py-20 text-center">
        <span className="text-xs font-medium uppercase tracking-wide" style={{ color: "#FF5A36" }}>Pricing</span>
        <h2 className="ev-display text-4xl md:text-5xl mt-2 mb-8">
          One plan, built for one attorney.
        </h2>
        <div className="bg-white rounded-2xl border border-line p-8 md:p-10 text-left">
          <div className="flex items-baseline justify-between mb-1">
            <span className="ev-wordmark text-[22px] tracking-[0.06em]">Starter</span>
            <span className="ev-display text-5xl">$199<span className="text-sm text-mute font-normal">/mo</span></span>
          </div>
          <p className="text-sm text-mute mb-6">7-day free trial. Card required at signup, no charge until the trial ends. Cancel anytime.</p>
          <ul className="flex flex-col gap-2.5 mb-7">
            <DoesItem text="One attorney, one jurisdiction — find, sell, and close to the consult" />
            <DoesItem text="Four CRM tabs you watch: Cold, In progress, Offer made, Done" />
            <DoesItem text="Complete audit trail on every conversation" />
            <DoesItem text="AI disclosure badge and compliance disclaimer, built in" />
          </ul>
          <button
            onClick={() => navigate(primaryCtaTarget)}
            className="w-full text-sm font-bold uppercase tracking-wide px-5 py-3 rounded-full flex items-center justify-center gap-2"
            style={{ backgroundColor: "#C6FF00", color: "#0B0B0D" }}
          >
            Start your 7-day free trial <ArrowRight size={15} />
          </button>
        </div>
        <p className="text-xs text-clay mt-5">
          Multi-attorney support is on our roadmap — reach out and we'll let you know when it's ready for your firm.
        </p>
      </section>

      <section id="faq" className="bg-white border-t border-line">
        <div className="max-w-2xl mx-auto px-6 py-16 md:py-20">
          <span className="text-xs font-medium uppercase tracking-wide" style={{ color: "#FF5A36" }}>FAQ</span>
          <h2 className="ev-display text-4xl md:text-5xl mt-2 mb-6">Questions attorneys ask first</h2>
          <div>
            <FaqItem
              q="Is this a product only for lawyers?"
              a="No. Law is an early market door. The engine has no lawyer-only branch. It reads how you describe the practice, then finds and sells like it would for any service business."
            />
            <FaqItem
              q="Do people already have to write in?"
              a="No. Cold is people found in the open web after the packet is analyzed — not visitors who filled a form. A chat widget on your site is only a conversation channel if someone already there wants to talk."
            />
            <FaqItem
              q="Is this actually compliant with my state's bar rules?"
              a={`Evorove is built to support the disclosure requirements already in effect in states like California (SB 243) and New York (Article 47) — the AI identifies itself clearly, includes a "not legal advice" notice, and safety or identity conflicts still stop the engine. Bar rules vary by state, and we'd always recommend a quick read of your own state's guidance before launch — we're not your compliance counsel.`}
            />
            <FaqItem
              q="Can the AI give legal advice by accident?"
              a="No — and that's the point. The agent phrases an approved sales move. It has no path to invent legal analysis, estimate outcomes, or promise results, because that capability isn't built into the message pipeline at all."
            />
            <FaqItem q="How long does setup take?" a="About 20 minutes for a single-attorney practice. No developer needed. Advertising materials can be added later — press Refresh so the engine uses them." />
            <FaqItem
              q="What if I want more than one attorney on the account?"
              a="Multi-attorney support is on our roadmap — reach out and we'll let you know when it's ready for your firm."
            />
          </div>
        </div>
      </section>

      <section className="max-w-4xl mx-auto px-6 py-20 md:py-28 text-center">
        <h2 className="ev-display text-5xl md:text-6xl mb-4">
          Open the board.<br />The cold ones are already there.
        </h2>
        <p className="text-mute mb-8 max-w-md mx-auto">7-day free trial. The sale until they are ready. No prompt to write.</p>
        <button
          onClick={() => navigate(primaryCtaTarget)}
          className="text-sm font-bold uppercase tracking-wide px-6 py-3.5 rounded-full inline-flex items-center gap-2"
          style={{ backgroundColor: "#C6FF00", color: "#0B0B0D" }}
        >
          Start your 7-day free trial <ArrowRight size={15} />
        </button>
      </section>

      <MarketingFooter extra={<span>Find · sell · close</span>} />
    </div>
  );
}
