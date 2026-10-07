import assert from "node:assert/strict";
import test from "node:test";
import { mailboxConnectionRequest, type MailboxDraft } from "./mailboxForm.ts";

function draft(overrides: Partial<MailboxDraft> = {}): MailboxDraft {
  return {
    fromAddress: "alena@getevorove.com",
    fromName: "Alena at Evorove",
    postalAddress: "100 Main St, Springfield, IL 62701",
    smtpHost: "smtp.zoho.com",
    smtpPort: "465",
    smtpSecurity: "ssl",
    smtpUsername: "alena@getevorove.com",
    password: "app-password-1",
    imapHost: "imap.zoho.com",
    imapPort: "993",
    dailyLimit: "30",
    ...overrides,
  };
}

test("builds the connect-email body the API already accepts", () => {
  const body = mailboxConnectionRequest(draft());
  assert.equal(typeof body, "object");
  assert.deepEqual(body, {
    from_address: "alena@getevorove.com",
    from_name: "Alena at Evorove",
    postal_address: "100 Main St, Springfield, IL 62701",
    smtp_host: "smtp.zoho.com",
    smtp_port: 465,
    smtp_security: "ssl",
    smtp_username: "alena@getevorove.com",
    password: "app-password-1",
    imap_host: "imap.zoho.com",
    imap_port: 993,
    daily_limit: 30,
  });
});

test("refuses a short postal address and a missing reply inbox", () => {
  assert.match(String(mailboxConnectionRequest(draft({ postalAddress: "PO" }))), /Postal address/);
  assert.match(String(mailboxConnectionRequest(draft({ imapHost: "  " }))), /IMAP host/);
  assert.match(String(mailboxConnectionRequest(draft({ password: "" }))), /password/);
});
