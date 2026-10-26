# Evorove — social presence and posting structure

Operator checklist for Evorove social. Customer-facing copy stays English. I cannot create or log into social accounts; pages below that are not already live must be claimed by Alena.

Posting runs through **n8n**, not Zapier. The agent writes a row in the Google Sheet. n8n reads `Ready` rows and publishes. Do not call Zapier skills, Typefully, LinkedIn, or X from this pipeline.

## Live posting (n8n)

Workflow: `https://n8n-production-69cd6.up.railway.app/workflow/9USkeF1v31mHqLai`  
Queue: [Evorove Content Queue](https://docs.google.com/spreadsheets/d/1_vMjKrIv-q9XpBT4gmAqC5sbkWW0VX4i-ZTMsm6MtDw/edit?gid=0#gid=0)

| channel | Network | Image |
| --- | --- | --- |
| `bluesky` | Bluesky `evorove.bsky.social` | Optional public HTTPS. Keep `post_text` ≤ 300 characters |
| `facebook` | Facebook Page | Optional public HTTPS (landing / framed shot) |
| `instagram` | Instagram Business | **Required** public HTTPS. Prefer square (`oct6_card_square.png`) |

Do not queue `linkedin` or `x`. Those networks are not in this n8n workflow.

Switch in n8n on column `channel`:

- `bluesky` → Bluesky create post (text + optional image)
- `facebook` → Facebook Graph: page post (`message` = `post_text`, photo = `image_url` when set)
- `instagram` → Instagram Graph: create media container from `image_url`, then publish with `post_text` as caption

Instagram will fail if `image_url` is empty or not publicly fetchable. Facebook and Bluesky may post text-only.

## What is already live

| Surface | Status | Handle / URL | In n8n |
| --- | --- | --- | --- |
| Bluesky | Connected | `evorove.bsky.social` | yes |
| Facebook Page | Connected | Evorove page on the Meta credential in n8n | yes |
| Instagram | Connected | Instagram Business linked to that Page | yes |
| LinkedIn company | Exists | [EVOROVE](https://www.linkedin.com/company/evorove) | no |
| LinkedIn personal | Exists | Alena Vorobei | no |
| X / Twitter | Exists | [@evorove_ai](https://x.com/evorove_ai) | no |
| GitHub repo | Exists | [AleneSparrow/Evorove](https://github.com/AleneSparrow/Evorove) | no |

## Profile copy (English, all networks)

**Name:** Evorove

**Headline / bio (short):**
Find. Sell. Book the hour. Not a CRM. Not a chatbot you prompt.

**About:**
Evorove is three cycles: find the person, sell until they are ready to book, then CRM puts the hour on the calendar. Finding people is the next contour — not shipped yet. The agent talks until the person is ready. Building in public. Unfinished. End-customer payment collection is not connected yet.

Do not use “cold lead”, CRM, chatbot, or intake assistant in bios.

**Brand book:** `docs/brand/evorove-pulse-brandbook.html`  
**Avatar (round crop, mark only):** `docs/brand/social/evorove-avatar.png`  
**Open Graph:** `docs/brand/social/evorove-og.png`

Do not upload `evorove-avatar-lockup.png` as a profile photo — the wordmark is cropped off in a circle. Full kit list: `docs/brand/social/README.md`. After frontend deploy, files are also at `/brand/...` on the site.

## Content queue structure

Google Sheet **Evorove Content Queue**, tab `Sheet1`. n8n reads this sheet. Status `Ready` is what it picks up.

| Column | Use |
| --- | --- |
| publish_date | When the row may go out (`YYYY-MM-DD`) |
| channel | `bluesky`, `facebook`, or `instagram` |
| audience | `brand` for the company accounts in n8n |
| status | `Draft` / `Ready` / `Posted` / `Skip` |
| post_text | Exact copy. n8n must not rewrite it |
| cta_url | Empty on intro/build posts |
| image_url | Public HTTPS PNG/JPG. Local paths do not post |
| posted_url | Filled after a successful post |
| notes | Asset filename, freeze flags |

Sales freeze still holds: no `$199`, no trial, no first-impression URL card.

## Oct 6 — landing chat example

Copy is English. One row per channel. `audience=brand`, `status=Ready`, `cta_url` empty.

**bluesky** (≤ 300 characters)

The landing now shows the chat.

Four tabs. The thread sits next to them. The engine writes. You watch.

Architecture sandbox. Frontend still private beta.

Image: `https://evorove.com/brand/evorove-oct6-card-tabs.png` (live fetch until deploy: `https://litter.catbox.moe/g78hqp.png`)

**facebook** — native Page photo. Ranking here is comments + time on the post, not hashtags. First line must earn “See more”. No outbound link.

You can watch the sale from the homepage.

Not a pitch deck. The landing is the board: Cold, In progress, Offer made, Done — and the actual thread sitting next to the tabs. The engine writes. Someone answers. You do not hop in to close.

This is the V1.0 architecture sandbox. Frontend is still private beta. Client 0 is Evorove selling Evorove, on the same board, with the same rules.

Be honest: if you opened your CRM at 11am, would you see this thread, or last night’s snapshot?

Image: `https://evorove.com/brand/evorove-oct6-site-hero.png` (live fetch until deploy: `https://litter.catbox.moe/qotchy.png`)

**instagram** — Feed. Saves and shares beat likes. If n8n can send a carousel, use four slides (swipe = dwell). If it is one photo, use the thread, not the empty square poster.

Caption (hook is line 1, before “… more”):

You can see the chat on the homepage now.

Most sites describe the product.
This one shows the thread.

Cold. In progress. Offer made. Done.
The engine writes. The reply comes back. You watch.

V1.0 architecture sandbox. Frontend still private beta. Client 0 is us selling us — same board, same rules.

Would you rather watch the sale live, or get the recap after it already went quiet?

Carousel (order matters — slide 1 stops the scroll):
1. `oct6_site_hero.png` — chat on the live landing
2. `oct6_site_board.png` — the thread
3. `oct6_site_board_cold.png` — Cold, not written yet
4. `oct6_card_tabs.png` — the four tabs, the saveable slide

Single-image fallback: `https://evorove.com/brand/evorove-oct6-site-board.png` (live fetch until deploy: `https://litter.catbox.moe/iger3a.png`)

Story (same day, not the feed post): `oct6_card_story.png` — “Not a pretty empty site.” Stick a poll: Live board / Evening report.

Files live under `web/app/public/brand/social/oct6/` so n8n can fetch them after deploy.

## Multimedia

| File | Use on |
| --- | --- |
| `oct6_card_framed.png` | Facebook — chat on the landing |
| `oct6_card_tabs.png` | Bluesky — four tabs |
| `oct6_card_square.png` | Instagram square |
| `oct6_site_hero.png` | Alternate landing shot |
| `evorove-post-inquiry-cycle.png` | Brand intro: inquiry in / booked job out |
| `evorove-ig-square.png` | Square feed fallback |
| `evorove-avatar.png` | Profile photo on every new network (mark only) |

Series source: `docs/marketing/project-history-50-social-posts-en.md`. Current product name in that series is Evorove.
