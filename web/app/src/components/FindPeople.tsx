import { useEffect, useState, type FormEvent } from "react";
import { Loader2, Search } from "lucide-react";
import { useAuth, describeError } from "../auth/AuthContext";
import { api, type LeadSearchStatus } from "../api/client";

const SEARCH_ACTIVE = new Set(["queued", "running"]);

function searchMessage(search: LeadSearchStatus | null): string {
  if (!search || search.status === "never_run") {
    return "Paste your website and we will look for people who need what you sell.";
  }
  if (search.status === "not_set_up") return "People search isn't connected yet.";
  if (SEARCH_ACTIVE.has(search.status)) return "Searching from your site… new people will appear on Cold.";
  if (search.status === "failed") return "The last search didn't finish. Try again.";
  const when = search.last_run_at ? new Date(search.last_run_at).toLocaleString("en-US") : "";
  if (search.cold > 0) return `Last search found ${search.cold} new ${search.cold === 1 ? "person" : "people"}${when ? ` · ${when}` : ""}.`;
  return `Last search found nobody new who fits${when ? ` · ${when}` : ""}. We search again every day.`;
}

export function FindPeople({ onFound }: { onFound: () => void }) {
  const { token, businessId } = useAuth();
  const [search, setSearch] = useState<LeadSearchStatus | null>(null);
  const [siteUrl, setSiteUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!token || !businessId) return;
    api
      .getLeadSearch(token, businessId)
      .then((res) => {
        setSearch(res);
        if (res.site_url) setSiteUrl((current) => current || res.site_url || "");
      })
      .catch(() => setSearch(null));
  }, [token, businessId]);

  useEffect(() => {
    if (!token || !businessId || !search || !SEARCH_ACTIVE.has(search.status)) return;
    const timer = window.setTimeout(() => {
      api
        .getLeadSearch(token, businessId)
        .then((res) => {
          setSearch(res);
          if (!SEARCH_ACTIVE.has(res.status)) onFound();
        })
        .catch((err) => setError(describeError(err)));
    }, 5000);
    return () => window.clearTimeout(timer);
  }, [token, businessId, search, onFound]);

  async function start(event: FormEvent) {
    event.preventDefault();
    if (!token || !businessId || !siteUrl.trim()) return;
    setSending(true);
    setError(null);
    try {
      setSearch(await api.startLeadSearch(token, businessId, siteUrl.trim()));
    } catch (err) {
      setError(describeError(err));
    } finally {
      setSending(false);
    }
  }

  const active = !!search && SEARCH_ACTIVE.has(search.status);
  const disabled = sending || active || search?.status === "not_set_up";
  return (
    <form onSubmit={start} className="px-5 py-4 border-b border-line flex flex-col gap-3">
      <div className="flex flex-col sm:flex-row gap-2">
        <input
          type="url"
          required
          value={siteUrl}
          onChange={(event) => setSiteUrl(event.target.value)}
          placeholder="https://your-business.com"
          aria-label="Your website"
          className="flex-1 min-w-0 px-3 py-2 rounded-lg border border-line text-sm"
        />
        <button
          type="submit"
          disabled={disabled}
          className="px-4 py-2 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
          style={{ backgroundColor: "#C6FF00", color: "#0B0B0D" }}
        >
          {active || sending ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
          Find people
        </button>
      </div>
      <p className="text-xs text-mute">{error ?? searchMessage(search)}</p>
    </form>
  );
}
