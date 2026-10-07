import { useEffect, useState, type FormEvent } from "react";
import { Loader2, Mail } from "lucide-react";
import { useAuth, describeError } from "../auth/AuthContext";
import { api, type MailboxStatus } from "../api/client";
import { Field, inputCls } from "./Shared";
import { mailboxConnectionRequest, type MailboxDraft, type SmtpSecurity } from "../lib/mailboxForm";

const EMPTY: MailboxDraft = {
  fromAddress: "",
  fromName: "",
  postalAddress: "",
  smtpHost: "",
  smtpPort: "587",
  smtpSecurity: "starttls",
  smtpUsername: "",
  password: "",
  imapHost: "",
  imapPort: "993",
  dailyLimit: "30",
};

function draftFromStatus(status: MailboxStatus): MailboxDraft {
  if (!status.connected) return EMPTY;
  return {
    fromAddress: status.from_address ?? "",
    fromName: status.from_name ?? "",
    postalAddress: status.postal_address ?? "",
    smtpHost: status.smtp_host ?? "",
    smtpPort: String(status.smtp_port ?? 587),
    smtpSecurity: status.smtp_security === "ssl" ? "ssl" : "starttls",
    smtpUsername: status.smtp_username ?? "",
    password: "",
    imapHost: status.imap_host ?? "",
    imapPort: String(status.imap_port ?? 993),
    dailyLimit: String(status.daily_limit ?? 30),
  };
}

export function MailboxPanel() {
  const { token, businessId } = useAuth();
  const [status, setStatus] = useState<MailboxStatus | null>(null);
  const [draft, setDraft] = useState<MailboxDraft>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  useEffect(() => {
    if (!token || !businessId) return;
    let cancelled = false;
    setLoading(true);
    api
      .getMailbox(token, businessId)
      .then((next) => {
        if (cancelled) return;
        setStatus(next);
        setDraft(draftFromStatus(next));
      })
      .catch((err) => {
        if (!cancelled) setError(describeError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, businessId]);

  function patch(partial: Partial<MailboxDraft>) {
    setDraft((current) => ({ ...current, ...partial }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!token || !businessId) return;
    const body = mailboxConnectionRequest(draft);
    if (typeof body === "string") {
      setError(body);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const next = await api.connectMailbox(token, businessId, body);
      setStatus(next);
      setDraft(draftFromStatus(next));
      setConfirmDisconnect(false);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setSaving(false);
    }
  }

  async function disconnect() {
    if (!token || !businessId) return;
    setSaving(true);
    setError(null);
    try {
      const next = await api.disconnectMailbox(token, businessId);
      setStatus(next);
      setDraft(EMPTY);
      setConfirmDisconnect(false);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-mute py-6">
        <Loader2 size={16} className="animate-spin" /> Checking the mailbox…
      </div>
    );
  }

  return (
    <form onSubmit={save}>
      <p className="text-sm text-mute mb-6 max-w-xl">
        The engine writes the first letter from this mailbox and reads the reply back onto the same card.
        Cold people get email, never a text. The password is stored encrypted and is not shown again.
      </p>
      {status?.connected && (
        <div className="flex items-center gap-3 p-4 rounded-xl border mb-6" style={{ borderColor: "#E4DCCB" }}>
          <span className="flex items-center justify-center rounded-full shrink-0" style={{ width: 36, height: 36, backgroundColor: "#E9F5EF", color: "#1E7B52" }}>
            <Mail size={16} />
          </span>
          <div>
            <div className="text-sm font-medium">{status.from_address}</div>
            <div className="text-xs text-mute mt-0.5">
              {status.sent_today} sent today · cap {status.todays_cap ?? status.daily_limit}. Enter the password again only when you save a change.
            </div>
          </div>
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-x-6 max-w-3xl">
        <Field label="From address" hint="The address the person sees.">
          <input className={inputCls} type="email" autoComplete="off" value={draft.fromAddress} onChange={(e) => patch({ fromAddress: e.target.value })} />
        </Field>
        <Field label="From name">
          <input className={inputCls} value={draft.fromName} onChange={(e) => patch({ fromName: e.target.value })} />
        </Field>
        <div className="md:col-span-2">
          <Field label="Postal address" hint="Printed at the bottom of every letter. At least 10 characters.">
            <input className={inputCls} value={draft.postalAddress} onChange={(e) => patch({ postalAddress: e.target.value })} />
          </Field>
        </div>
        <Field label="SMTP host">
          <input className={inputCls} value={draft.smtpHost} onChange={(e) => patch({ smtpHost: e.target.value })} placeholder="smtp.example.com" />
        </Field>
        <Field label="SMTP port">
          <input className={inputCls} inputMode="numeric" value={draft.smtpPort} onChange={(e) => patch({ smtpPort: e.target.value })} />
        </Field>
        <Field label="SMTP security">
          <select
            className={inputCls}
            value={draft.smtpSecurity}
            onChange={(e) => patch({ smtpSecurity: e.target.value as SmtpSecurity })}
          >
            <option value="starttls">STARTTLS (usually 587)</option>
            <option value="ssl">SSL (usually 465)</option>
          </select>
        </Field>
        <Field label="SMTP username">
          <input className={inputCls} autoComplete="off" value={draft.smtpUsername} onChange={(e) => patch({ smtpUsername: e.target.value })} />
        </Field>
        <Field label="Password" hint="You type it. The screen never shows the saved one.">
          <input className={inputCls} type="password" autoComplete="new-password" value={draft.password} onChange={(e) => patch({ password: e.target.value })} />
        </Field>
        <Field label="Daily send cap">
          <input className={inputCls} inputMode="numeric" value={draft.dailyLimit} onChange={(e) => patch({ dailyLimit: e.target.value })} />
        </Field>
        <Field label="IMAP host" hint="Where replies are read.">
          <input className={inputCls} value={draft.imapHost} onChange={(e) => patch({ imapHost: e.target.value })} placeholder="imap.example.com" />
        </Field>
        <Field label="IMAP port">
          <input className={inputCls} inputMode="numeric" value={draft.imapPort} onChange={(e) => patch({ imapPort: e.target.value })} />
        </Field>
      </div>
      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg text-sm max-w-3xl" style={{ backgroundColor: "#FBEBE9", color: "#8A3225" }}>
          {error}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={saving}
          className="text-sm font-medium text-white px-4 py-2.5 rounded-lg flex items-center gap-1.5 disabled:opacity-50"
          style={{ backgroundColor: "#0B0B0D" }}
        >
          {saving && <Loader2 size={13} className="animate-spin" />}
          {status?.connected ? "Save mailbox" : "Connect mailbox"}
        </button>
        {status?.connected && !confirmDisconnect && (
          <button type="button" className="text-sm font-medium text-clay px-3 py-2.5" onClick={() => setConfirmDisconnect(true)}>
            Disconnect
          </button>
        )}
        {status?.connected && confirmDisconnect && (
          <button type="button" disabled={saving} className="text-sm font-medium px-3 py-2.5" style={{ color: "#8A3225" }} onClick={disconnect}>
            Disconnect this mailbox. Letters stop until you connect it again.
          </button>
        )}
      </div>
    </form>
  );
}
