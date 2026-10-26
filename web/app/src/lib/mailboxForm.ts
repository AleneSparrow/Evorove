/** Settings → Mailbox. Builds the existing connect-email body. The password is write-only. */

export type SmtpSecurity = "ssl" | "starttls";

export interface MailboxDraft {
  fromAddress: string;
  fromName: string;
  postalAddress: string;
  smtpHost: string;
  smtpPort: string;
  smtpSecurity: SmtpSecurity;
  smtpUsername: string;
  password: string;
  imapHost: string;
  imapPort: string;
  dailyLimit: string;
}

export interface MailboxConnectionRequest {
  from_address: string;
  from_name: string;
  postal_address: string;
  smtp_host: string;
  smtp_port: number;
  smtp_security: SmtpSecurity;
  smtp_username: string;
  password: string;
  imap_host: string;
  imap_port: number;
  daily_limit: number;
}

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function port(value: string, label: string): number | string {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    return `${label} needs a port from 1 to 65535.`;
  }
  return parsed;
}

/** A ready request, or one sentence the owner can fix. */
export function mailboxConnectionRequest(draft: MailboxDraft): MailboxConnectionRequest | string {
  const fromAddress = draft.fromAddress.trim();
  const fromName = draft.fromName.trim();
  const postalAddress = draft.postalAddress.trim();
  const smtpHost = draft.smtpHost.trim();
  const smtpUsername = draft.smtpUsername.trim();
  const imapHost = draft.imapHost.trim();
  const password = draft.password;
  if (!EMAIL.test(fromAddress)) return "From address needs to be an email.";
  if (!fromName) return "From name is required.";
  if (postalAddress.length < 10) {
    return "Postal address needs at least 10 characters. It is printed on every letter.";
  }
  if (!smtpHost) return "SMTP host is required.";
  const smtpPort = port(draft.smtpPort, "SMTP");
  if (typeof smtpPort === "string") return smtpPort;
  if (draft.smtpSecurity !== "ssl" && draft.smtpSecurity !== "starttls") {
    return "Choose SSL or STARTTLS.";
  }
  if (!smtpUsername || !password) return "SMTP username and password are required.";
  if (!imapHost) return "IMAP host is required so a reply lands on the same card.";
  const imapPort = port(draft.imapPort, "IMAP");
  if (typeof imapPort === "string") return imapPort;
  const dailyLimit = Number(draft.dailyLimit);
  if (!Number.isInteger(dailyLimit) || dailyLimit < 1 || dailyLimit > 500) {
    return "Daily limit needs to be a whole number from 1 to 500.";
  }
  return {
    from_address: fromAddress,
    from_name: fromName,
    postal_address: postalAddress,
    smtp_host: smtpHost,
    smtp_port: smtpPort,
    smtp_security: draft.smtpSecurity,
    smtp_username: smtpUsername,
    password,
    imap_host: imapHost,
    imap_port: imapPort,
    daily_limit: dailyLimit,
  };
}
