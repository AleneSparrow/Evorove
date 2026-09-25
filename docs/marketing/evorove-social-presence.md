# Evorove — social presence and posting structure

Operator checklist for Evorove social. Customer-facing copy stays English. I cannot create or log into social accounts; pages below that are not already live must be claimed by Alena.

## What is already live

| Surface | Status | Handle / URL | Zapier posting |
| --- | --- | --- | --- |
| LinkedIn company | Created | [EVOROVE](https://www.linkedin.com/company/evorove) (`company_id` `143660972`) | Skill **evorove linkedin company autopost** |
| LinkedIn personal | Connected | Alena Vorobei | Founder-sv only, skill **evorove linkedin founder autopost** |
| X / Twitter | Brand connected via Typefully | [@evorove_ai](https://x.com/evorove_ai) on social set `330124` (Evorove) | Ready. Personal [@AleneVorobei](https://x.com/AleneVorobei) is not on this Typefully set |
| GitHub repo | Exists | [AleneSparrow/Evorove](https://github.com/AleneSparrow/Evorove) | App enabled; needs auth |

## Claim these handles as `evorove`

Create the page yourself, then say **done** and I will connect posting. Do not invent a second product name.

| Network | Create | Suggested handle | After create |
| --- | --- | --- | --- |
| X | Brand account | `@evorove_ai` (live) | Connected on Typefully social set `330124` (Evorove) |
| YouTube | Channel | Evorove | [Connect YouTube](https://mcp.zapier.com/api/v1/connect-auth/YouTubeV4CLIAPI?accountId=28487181) |
| Bluesky | Profile | `evorove.bsky.social` | [Connect Bluesky](https://mcp.zapier.com/api/v1/connect-auth/App216613CLIAPI?accountId=28487181) **or** add the account in Typefully (Typefully can post Bluesky from the same draft) |
| GitHub | Organization `evorove` (optional; repo already uses the name) | [Connect GitHub](https://mcp.zapier.com/api/v1/connect-auth/GitHubCLIAPI?accountId=28487181) |
| Discord | Server named Evorove | Create the server, then connect Discord in Zapier |
| Product Hunt | Maker / upcoming product | `evorove` | Manual launch later; Zapier has read-only Product Hunt |
| Reddit | User `u/evorove` | Do not autopost. Use for AMA / comments only |
| Mastodon | Profile on a tech instance | Add in Typefully if you want a third text network |
| Threads | Profile | Add in Typefully if you want it |
| Buffer | Optional hub for extra networks | [Connect Buffer](https://mcp.zapier.com/api/v1/connect-auth/BufferCLIAPI?accountId=28487181) |
| Facebook Page | Only if you want a page named Evorove | [Connect Facebook Pages](https://mcp.zapier.com/api/v1/connect-auth/FacebookV2CLIAPI?accountId=28487181) |
| Instagram | Only if you want a brand visual account | Needs a Facebook Page first. [Connect Instagram](https://mcp.zapier.com/api/v1/connect-auth/InstagramBusinessCLIAPI?accountId=28487181) |

Priority for a US tech SaaS: **LinkedIn company (done) → X `@evorove_ai` (done) → YouTube → Bluesky → GitHub org → Discord**. Facebook/Instagram are optional, not the core tech surface.

## Profile copy (English, all networks)

**Name:** Evorove

**Headline / bio (short):**
Find. Sell. Book the hour. Not a CRM. Not a chatbot you prompt.

**About (LinkedIn / YouTube):**
Evorove is three cycles: find the person, sell until they are ready to book, then CRM puts the hour on the calendar. Finding people is the next contour — not shipped yet. The agent talks until the person is ready. Building in public. Unfinished. End-customer payment collection is not connected yet.

Do not use “cold lead”, CRM, chatbot, or intake assistant in bios.

**Brand book:** `docs/brand/evorove-pulse-brandbook.html`  
**Avatar (round crop, mark only):** `docs/brand/social/evorove-avatar.png`  
**LinkedIn banner:** `docs/brand/social/evorove-linkedin-banner.png` (company cover 4200×700, not personal 1584×396)  
**X header:** `docs/brand/social/evorove-x-header.png`  
**YouTube art:** `docs/brand/social/evorove-youtube-banner.png`  
**Open Graph:** `docs/brand/social/evorove-og.png`

Do not upload `evorove-avatar-lockup.png` as a profile photo — the wordmark is cropped off in a circle. Full kit list: `docs/brand/social/README.md`. After frontend deploy, files are also at `/brand/...` on the site.

## Content queue structure

Table `01M1N9VBC7JMDFM9QSMKZNMQM8` — Evorove content queue. Zapier Tables has no rename-table API, so the UI title may still say Flywheel until you rename it in [Zapier Tables](https://tables.zapier.com). Skills use the table id, not the title.

| Field | Key | Use |
| --- | --- | --- |
| publish_date | f1 | When the row may go out |
| channel | f2 | `linkedin`, `x`, or `bluesky` |
| audience | f3 | `brand` → EVOROVE company page; `founder-sv` → personal; `wave1-lawyers` stays Draft |
| status | f4 | Draft / Ready / Posted / Skip |
| post_text | f5 | Exact copy. Autopost never rewrites it |
| cta_url | f6 | Empty on intro/build posts |
| image_url | f7 | Public HTTPS URL of a PNG/JPG. Local paths do not post |
| posted_url | f8 | Filled after a successful post |
| notes | f9 | Asset filename, freeze flags, `BLOCK_AUTOPOST_UNTIL_*` |

Sales freeze still holds: no `$199`, no trial, no first-impression URL card.

## Multimedia for upcoming posts

Local files (fill `image_url` after they are on HTTPS):

| File | Use on |
| --- | --- |
| `evorove-post-inquiry-cycle.png` | Brand intro: inquiry in / booked job out |
| `evorove-post-capture-vs-cycle.png` | Capture vs cycle distinction (was C-02) |
| `evorove-post-engine-decides.png` | Model rewrites / engine decides |
| `evorove-post-same-dna.png` | Same engine, new DNA |
| `evorove-post-not-a-chat.png` | Not a chat window |
| `evorove-post-dead-air.png` | Dead air is a product bug |
| `evorove-post-follow-up.png` | Cycle does not stop at the form |
| `evorove-post-building.png` | Unfinished, on purpose |
| `evorove-ig-square.png` | Square feed / Instagram |
| `evorove-story-*.png` | Stories / Reels covers |
| `evorove-still-torus-*.png` | Campaign stills, no type |
| `evorove-linkedin-banner.png` | Company page cover, not a feed post |
| `evorove-avatar.png` | Profile photo on every new network (mark only) |
| `evorove-x-header.png` | X brand account header |

Series source: `docs/marketing/project-history-50-social-posts-en.md`. Current product name in that series is Evorove. Post 29 keeps the historical Atelier → Flywheel chapter. Post 51 is the public rename to Evorove.

## Zapier skills

- **evorove linkedin company autopost** — Ready `linkedin` + `brand` → company `143660972`, image from f7
- **evorove linkedin founder autopost** — Ready `linkedin` + `founder-sv` → personal profile
- **evorove x typefully autopost** — Ready `x` → Typefully set `330124` (Evorove / `@evorove_ai`)
- **evorove bluesky autopost** — Ready `bluesky` → `evorove.bsky.social` via `bluesky_create_standalone_image_post` (text + optional image). Do not use stock `bluesky_create_post` for images: Zapier treats reply `"false"` as a reply and demands `replyToUri` / `replyToCid`.

Do not turn on Zap `378524885` until it is remapped to Evorove and the company page.

## Typefully

Social set `330124` has X = **@evorove_ai**. If the Typefully UI still shows “Alena Vorobei”, rename the set to **Evorove** in Typefully (I cannot log in). LinkedIn / Bluesky / Threads / Mastodon are not connected on that set. Brand X posts use this set. If Alena still needs to schedule to personal @AleneVorobei, create a second Typefully social set for that handle.
