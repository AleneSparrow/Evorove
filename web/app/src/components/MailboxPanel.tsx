import { useEffect, useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { api, type EmailConnectionInput, type EmailConnectionStatus } from "../api/client";
import { describeError } from "../auth/AuthContext";
import { Field, inputCls } from "./Shared";

type Security = EmailConnectionInput["smtp_security"];

interface MailboxForm {
  from_name: string;
  from_address: string;
  postal_address: string;
  smtp_host: string;
  smtp_port: string;
  smtp_security: Security;
  smtp_username: string;
  password: string;
  imap_host: string;
  imap_port: string;
  daily_limit: string;
}

const EMPTY: MailboxForm = {
  from_name: "",
  from_address: "",
  postal_address: "",
  smtp_host: "",
  smtp_port: "465",
  smtp_security: "ssl",
  smtp_username: "",
  password: "",
  imap_host: "",
  imap_port: "993",
  daily_limit: "30",
};

function formFromStatus(status: EmailConnectionStatus): MailboxForm {
  const security: Security = status.smtp_security === "starttls" ? "starttls" : "ssl";
  return {
    from_name: status.from_name ?? "",
    from_address: status.from_address ?? "",
    postal_address: status.postal_address ?? "",
    smtp_host: status.smtp_host ?? "",
    smtp_port: String(status.smtp_port ?? (security === "starttls" ? 587 : 465)),
    smtp_security: security,
    smtp_username: status.smtp_username ?? "",
    password: "",
    imap_host: status.imap_host ?? "",
    imap_port: String(status.imap_port ?? 993),
    daily_limit: String(status.daily_limit ?? 30),
  };
}

function portNumber(value: string): number | null {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) return null;
  return parsed;
}

export function MailboxPanel({ token, businessId }: { token: string; businessId: string }) {
  const [status, setStatus] = useState<EmailConnectionStatus | null>(null);
  const [form, setForm] = useState<MailboxForm>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.getEmailConnection(token, businessId)
      .then((next) => {
        if (cancelled) return;
        setStatus(next);
        setForm(next.connected ? formFromStatus(next) : EMPTY);
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

  const set = (patch: Partial<MailboxForm>) => {
    setSaved(false);
    setForm((current) => ({ ...current, ...patch }));
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSaved(false);
    if (form.postal_address.trim().length < 10) {
      setError("A physical postal address of at least 10 characters goes in every commercial email.");
      return;
    }
    if (!form.imap_host.trim() || portNumber(form.imap_port) === null) {
      setError("IMAP host and port are required so a reply lands back on the same card.");
      return;
    }
    const smtpPort = portNumber(form.smtp_port);
    const dailyLimit = Number(form.daily_limit);
    if (smtpPort === null || !Number.isInteger(dailyLimit) || dailyLimit < 1 || dailyLimit > 500) {
      setError("Check the SMTP port and the daily limit (1–500).");
      return;
    }
    if (!status?.connected && !form.password) {
      setError("The mailbox password is required the first time you connect.");
      return;
    }
    const body: EmailConnectionInput = {
      from_address: form.from_address.trim(),
      from_name: form.from_name.trim(),
      postal_address: form.postal_address.trim(),
      smtp_host: form.smtp_host.trim(),
      smtp_port: smtpPort,
      smtp_security: form.smtp_security,
      smtp_username: form.smtp_username.trim(),
      password: form.password,
      imap_host: form.imap_host.trim(),
      imap_port: portNumber(form.imap_port) as number,
      daily_limit: dailyLimit,
    };
    setSaving(true);
    try {
      const next = await api.connectEmail(token, businessId, body);
      setStatus(next);
      setForm(formFromStatus(next));
      setSaved(true);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setSaving(false);
    }
  };

  const disconnect = async () => {
    if (!window.confirm("Disconnect this mailbox? The engine stops sending until you connect it again.")) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const next = await api.disconnectEmail(token, businessId);
      setStatus(next);
      setForm(EMPTY);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-mute py-6">
        <Loader2 size={16} className="animate-spin" /> Checking the mailbox…
      </div>
    );
  }

  return (
    <form onSubmit={save} className="max-w-2xl">
      <p className="text-sm text-mute mb-6">
        The engine writes the cold letter from this mailbox and reads the reply back onto the same card.
        Leave the password blank when a mailbox is already saved — only a new password replaces it.
      </p>

      {status?.connected && status.send_block && (
        <div className="px-4 py-3 rounded-lg text-sm mb-5" style={{ backgroundColor: "#FBF3E8", color: "#8A5A1F" }}>
          The engine will not send yet: {status.send_block}
        </div>
      )}
      {status?.connected && !status.send_block && (
        <div className="px-4 py-3 rounded-lg text-sm mb-5" style={{ backgroundColor: "#E9F5EF", color: "#1E7B52" }}>
          Ready to send. Today's cap is {status.todays_cap ?? "-"}, sent {status.sent_today}.
        </div>
      )}
      {status?.connected && !status.replies_ready && (
        <div className="px-4 py-3 rounded-lg text-sm mb-5" style={{ backgroundColor: "#FBF3E8", color: "#8A5A1F" }}>
          Replies will not come back onto the card until IMAP host and port are saved.
        </div>
      )}
      {!status?.connected && (
        <div className="px-4 py-3 rounded-lg text-sm mb-5" style={{ backgroundColor: "#F1F1EF", color: "#6B6459" }}>
          No mailbox yet. Connect one before the first letter goes out.
        </div>
      )}

      <Field label="From name" hint="What the customer sees before the address.">
        <input className={inputCls} required maxLength={255} value={form.from_name} onChange={(e) => set({ from_name: e.target.value })} />
      </Field>
      <Field label="From address">
        <input className={inputCls} type="email" required maxLength={320} value={form.from_address} onChange={(e) => set({ from_address: e.target.value })} />
      </Field>
      <Field label="Postal address" hint="A real street address, at least 10 characters. It goes in the footer of every commercial email.">
        <textarea
          className={inputCls}
          required
          minLength={10}
          maxLength={500}
          rows={2}
          value={form.postal_address}
          onChange={(e) => set({ postal_address: e.target.value })}
        />
      </Field>

      <div className="grid sm:grid-cols-2 gap-x-4">
        <Field label="SMTP host">
          <input className={inputCls} required maxLength={255} placeholder="smtp.example.com" value={form.smtp_host} onChange={(e) => set({ smtp_host: e.target.value })} />
        </Field>
        <Field label="SMTP port" hint="465 for SSL, 587 for STARTTLS.">
          <input className={inputCls} required inputMode="numeric" value={form.smtp_port} onChange={(e) => set({ smtp_port: e.target.value })} />
        </Field>
      </div>
      <Field label="SMTP security">
        <select
          className={inputCls}
          value={form.smtp_security}
          onChange={(e) => set({ smtp_security: e.target.value === "starttls" ? "starttls" : "ssl" })}
        >
          <option value="ssl">SSL</option>
          <option value="starttls">STARTTLS</option>
        </select>
      </Field>
      <Field label="SMTP username">
        <input className={inputCls} required maxLength={320} autoComplete="username" value={form.smtp_username} onChange={(e) => set({ smtp_username: e.target.value })} />
      </Field>
      <Field
        label="Mailbox password"
        hint={status?.connected ? "Leave this blank to keep the password already saved." : "An app password from the mailbox provider. It is stored encrypted and never shown again."}
      >
        <input
          className={inputCls}
          type="password"
          autoComplete="new-password"
          maxLength={1024}
          required={!status?.connected}
          value={form.password}
          onChange={(e) => set({ password: e.target.value })}
        />
      </Field>

      <div className="grid sm:grid-cols-2 gap-x-4">
        <Field label="IMAP host" hint="Replies are read from here and attached to the same card.">
          <input className={inputCls} required maxLength={255} placeholder="imap.example.com" value={form.imap_host} onChange={(e) => set({ imap_host: e.target.value })} />
        </Field>
        <Field label="IMAP port">
          <input className={inputCls} required inputMode="numeric" value={form.imap_port} onChange={(e) => set({ imap_port: e.target.value })} />
        </Field>
      </div>
      <Field label="Daily limit" hint="Warm-up starts lower than this and climbs toward it.">
        <input className={inputCls} required inputMode="numeric" value={form.daily_limit} onChange={(e) => set({ daily_limit: e.target.value })} />
      </Field>

      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg text-sm" style={{ backgroundColor: "#FBEBE9", color: "#8A3225" }}>
          {error}
        </div>
      )}
      {saved && !status?.send_block && (
        <div className="mb-4 px-4 py-3 rounded-lg text-sm" style={{ backgroundColor: "#E9F5EF", color: "#1E7B52" }}>
          Mailbox saved.
        </div>
      )}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={saving}
          className="text-sm font-medium text-white px-4 py-2.5 rounded-lg flex items-center gap-1.5 disabled:opacity-50"
          style={{ backgroundColor: "#0B0B0D" }}
        >
          {saving && <Loader2 size={13} className="animate-spin" />}
          {status?.connected ? "Update mailbox" : "Connect mailbox"}
        </button>
        {status?.connected && (
          <button
            type="button"
            disabled={saving}
            onClick={() => void disconnect()}
            className="text-sm font-medium px-4 py-2.5 rounded-lg border border-line disabled:opacity-50"
          >
            Disconnect
          </button>
        )}
      </div>
    </form>
  );
}
