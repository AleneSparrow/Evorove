import { useEffect, useRef, useState, type FormEvent } from "react";
import { Loader2, RefreshCw, Upload } from "lucide-react";
import { api, type MarketingPacket } from "../api/client";
import { describeError } from "../auth/AuthContext";
import { Field, inputCls } from "./Shared";

export function MaterialsPanel({ token, businessId }: { token: string; businessId: string }) {
  const [packet, setPacket] = useState<MarketingPacket | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [kind, setKind] = useState<"notes" | "offer">("notes");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    api
      .getMarketingPacket(token, businessId)
      .then(setPacket)
      .catch((err) => setError(describeError(err)));
  };

  useEffect(() => {
    setError(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, businessId]);

  const run = async (work: () => Promise<MarketingPacket>, ok: string) => {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setPacket(await work());
      setMessage(ok);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  };

  const addText = (event: FormEvent) => {
    event.preventDefault();
    void run(
      () => api.addMarketingText(token, businessId, { kind, title, body_text: body }),
      "Saved as a draft. Press Refresh before the engine uses it.",
    ).then(() => {
      setTitle("");
      setBody("");
    });
  };

  const addFile = (file: File | undefined) => {
    if (!file) return;
    void run(
      () => api.addMarketingFile(token, businessId, file),
      "File added as a draft. Press Refresh before the engine uses it.",
    );
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-2xl border border-line bg-white p-5">
        <h2 className="text-base font-semibold">Materials library</h2>
        <p className="text-sm text-mute mt-1 leading-relaxed">
          Upload notes, a price list, photos, video, or a PDF as facts. The presentation move
          picks one relevant item. It will not invent a flyer or a discount.
        </p>
        {packet?.guidance && (
          <p className="text-xs text-mute mt-3" style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
            Live packet · revision {packet.guidance.revision} · {new Date(packet.guidance.activated_at).toLocaleString("en-US")}
          </p>
        )}
        {packet?.pending && (
          <p className="text-sm mt-3" style={{ color: "#8A561B" }}>Drafts are waiting. Refresh to put them in force.</p>
        )}
        <button
          type="button"
          disabled={busy || !packet}
          onClick={() => void run(() => api.activateMarketingPacket(token, businessId), "Live. The next presentation picks one fact from this packet.")}
          className="mt-4 inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50"
          style={{ backgroundColor: "#0B0B0D" }}
        >
          {busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Refresh
        </button>
      </div>

      {error && <div className="px-4 py-3 rounded-lg text-sm" style={{ backgroundColor: "#FBEBE9", color: "#8A3225" }}>{error}</div>}
      {message && <div className="px-4 py-3 rounded-lg text-sm" style={{ backgroundColor: "#E9F5EF", color: "#1E7B52" }}>{message}</div>}

      <form onSubmit={addText} className="rounded-2xl border border-line bg-white p-5">
        <h3 className="font-semibold mb-3">Add notes or an offer</h3>
        <div className="flex gap-2 mb-3">
          {(["notes", "offer"] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setKind(value)}
              className="px-3 py-1.5 rounded-full text-xs font-medium"
              style={{ backgroundColor: kind === value ? "#FFE8E1" : "transparent", color: kind === value ? "#FF5A36" : "#6B6459" }}
            >
              {value === "notes" ? "Business notes" : "Commercial offer"}
            </button>
          ))}
        </div>
        <Field label="Title">
          <input className={inputCls} value={title} maxLength={200} required onChange={(event) => setTitle(event.target.value)} />
        </Field>
        <Field label="Text">
          <textarea className={`${inputCls} min-h-[120px] resize-y`} value={body} required maxLength={20000} onChange={(event) => setBody(event.target.value)} />
        </Field>
        <button disabled={busy} className="px-4 py-2 rounded-lg text-sm text-white disabled:opacity-50" style={{ backgroundColor: "#0B0B0D" }}>
          Add to packet
        </button>
      </form>

      <div className="rounded-2xl border border-line bg-white p-5">
        <h3 className="font-semibold mb-1">Add multimedia or files</h3>
        <p className="text-sm text-mute mb-3">
          Text and PDF text become facts. Photos and video are stored as a labeled file — say in
          notes what they show if the sale needs that fact.
        </p>
        <input ref={fileRef} type="file" className="hidden" onChange={(event) => { addFile(event.target.files?.[0]); event.target.value = ""; }} />
        <button
          type="button"
          disabled={busy}
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm border border-line"
        >
          <Upload size={14} /> Upload another file
        </button>
      </div>

      <div className="rounded-2xl border border-line bg-white overflow-hidden">
        <div className="px-5 py-3 border-b border-line text-sm font-semibold">In this packet ({packet?.assets.length ?? 0})</div>
        {!packet ? (
          <div className="px-5 py-8 text-sm text-mute flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Loading…</div>
        ) : packet.assets.length === 0 ? (
          <p className="px-5 py-8 text-sm text-mute">Nothing uploaded yet.</p>
        ) : (
          <ul>
            {packet.assets.map((asset) => (
              <li key={asset.asset_id} className="px-5 py-3 border-b border-[#F0EFE9] last:border-0">
                <div className="text-sm font-medium">{asset.title} <span className="text-xs text-clay font-normal">· {asset.kind}</span></div>
                <p className="text-sm text-mute mt-1">{asset.body_preview}</p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
