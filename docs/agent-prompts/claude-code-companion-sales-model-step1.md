# Prompt for Claude Code: Step 1 companion sales model (7 September 2026)

Владелец переоткрыл отдельную модель. Это **шаг 1: легальный корпус +
датасет + eval**, не запуск training job и не утверждение карточек.

Скопируйте блок ниже в Claude Code из корня репозитория.

```text
Read AGENTS.md, CLAUDE.md, docs/sales-agent-implementation-plan-ru.md
(sections 0, 0.3, 0.4, 8, 21), docs/architecture/adr-0001-sales-conversation-layer.md,
src/domain/sales.py, src/engine/sales_policy.py,
docs/sales-knowledge/candidate-knowledge-cards-2026-09-04.md,
docs/agent-prompts/claude-code-sales-knowledge-and-evals-report-2026-09-04.md,
config/sales-knowledge/objection-handling-v1.json,
evals/sales_turn_analysis/, evals/sales_response_generation/.

You are building Step 1 of a companion specialist model that will later sit
beside the configured Evorove agent. You are not replacing the agent.

Hard boundaries
- SalesPolicyEngine chooses SalesMove, price, discount, booking, handoff.
  The companion only analyzes language and phrases an already-approved move.
- Do not approve, publish, or import knowledge cards into a tenant. Status
  stays candidate / unapproved. Owner does a separate review later.
- Do not modify ProcessState, StateMachine, ProcessEngine, SalesPolicyEngine
  transitions, database models, migrations, API contracts, or frontend.
- Do not start a GPU/hosted training job, upload weights, or change
  AI_PROVIDER. Step 2 is later.
- Do not promise or encode a 96% conversion rate in data, prompts, or
  marketing copy. Conversion is measured later as inquiry_to_deal_rate.
- Do not read, print, or edit .env or secrets. Do not git push.

Owner drop path (do not download books): private/sales-corpus/incoming/
then python scripts/ingest_sales_corpus.py
Guide: docs/sales-knowledge/how-to-deposit-books-ru.md

Legal corpus — non-negotiable
- Do NOT download, scrape, or reconstruct paywalled / pirated books
  (LibGen, Sci-Hub, Anna's Archive, "all textbooks on the internet",
  torrent, shared drives you do not own).
- Closed-access material is in-scope ONLY if the owner has already placed
  the file in private/sales-corpus/ and listed it in the manifest with a
  license note (purchase / publisher licence / "my copy").
- Open web: include a source only when you can record a working URL and
  a licence (CC, public domain, publisher terms that allow a short derived
  rule). If licence is unknown, list it in a "needs-owner-licence" queue
  instead of copying the text.
- Store derived rules and short paraphrases. Do not paste chapters, long
  quotations, or full PDFs into git.

Product posture already decided (section 0.4) — apply, do not reopen
- Acknowledge objections without arguing. No Feel-Felt-Found formula.
  Challenger reframe only with a Business DNA fact.
- Scarcity only with a verifiable slot/deadline fact; otherwise negative
  example, not a positive training target.
- Voss: one calibrated what/how question for DIAGNOSE_OBJECTION.
- Drop candidate-trial-time-to-value-007 from the corpus until a named
  source exists. Trial length is a DNA fact.
- Reciprocity / small-yes only when DNA already authorizes the free step.
- candidate-objection-script-feel-felt-found-CONTESTED-008 is not a
  positive example.

Reuse, do not redo blindly
- Keep existing SalesStage / SalesMove enums. Do not invent RAPPORT as a
  new stage unless the owner updates the spec and transition tests. Rapport
  / pacing lives in GREET_AND_SET_CONTEXT + tone, not a new enum.
- Existing candidate cards stay candidates. You may add NEW candidates from
  newly licensed sources. You may mark old ones as "aligned" or "conflicts
  with 0.4" in the catalog. You may not flip status to approved.
- objection-handling-v1.json is an operational pack, also not auto-approved
  for a tenant. You may cite it as a candidate source, not publish it.
- Prompts and evals already exist. Extend fixtures; do not weaken them so
  a model passes. Anthropic one-key wrapping is fixed in
  src/ai/anthropic_provider.py (unwrap_forced_tool_input) — do not "fix"
  it again in prompt text unless a new live failure appears.

Part 1 — source catalog
1. Scan private/sales-corpus/ (filenames and this-directory README only if
   files exist). Never commit those files.
2. Search openly licensed and clearly citable sales/persuasion sources:
   classic public-domain selling texts, CC-licensed practitioner articles,
   reputable open case write-ups, the owner's already-listed methodologies
   (SPIN, Challenger, Influence, Never Split the Difference) as
   catalog rows that still require a deposited copy for page-verified
   provenance.
3. Write docs/sales-knowledge/corpus-manifest-step1.md with one row per
   source: title, author, year, licence, URL or private filename, whether
   a copy is deposited, provenance_confidence (page-verified | title-only |
   needs-licence), proposed use (positive rule / negative counterexample /
   skip).
4. A "needs-licence" queue is a successful outcome. An invented library of
   unpaid PDFs is a failure.

Part 2 — candidate knowledge extraction
1. For every source that is deposited or openly licensed, create candidate
   SalesKnowledgeCard objects matching the project schema.
2. Exact provenance: title, chapter, page/section when a copy exists.
   If only title-level knowledge is available, say so and do not fake pages.
3. Separate the source's rule from your examples and from interpretation.
4. Omit a rule that the source does not actually state.
5. If a new source contradicts section 0.4, keep the 0.4 posture and record
   the source as a documented conflict. Do not "average" the two into a
   new approved method.
6. Every card: status candidate, version 0. No import API calls. No
   Settings approve.
7. Cover the live sales path, not a generic textbook TOC: greeting/context,
   discovery (one question), need confirm, relevant value, diagnose
   objection, answer from DNA + evidence, check resolution, small
   commitment, booking/next step, callback-as-our-follow-up, nurture,
   STOP/emergency/human.

Part 3 — training dataset shape (no weights)
1. Add docs/sales-knowledge/companion-dataset-spec.md describing JSONL
   records that map onto existing schemas only:
   - analyzer rows: customer_message + profile_context → SalesTurnAnalysis
     fields (evidence must be verbatim substrings).
   - generator rows: approved_move + allowed facts/evidence →
     SalesResponseOutput (move MUST equal approved_move).
2. Emit evals/companion_step1/fixtures.json (or extend the two existing
   eval folders) with positives AND negatives: discount demand, fake
   scarcity, Feel-Felt-Found, guarantee, prompt injection, STOP.
3. Put derived JSONL under evals/companion_step1/ or reports/, never under
   private/sales-corpus/. No full book text in those files.
4. Do not call a training vendor. End the report with: corpus size,
   licence breakdown, fixture counts, remaining needs-licence titles,
   and an explicit "ready for Step 2 training: yes/no" that is no unless
   the owner has deposited closed-access copies they want included.

Part 4 — leftover language evals
1. If Anthropic credentials are already available through normal runtime,
   re-run scripts/sales_turn_analysis_eval.py and
   scripts/sales_response_generation_eval.py. Never print secrets.
2. Record model, prompt version, pass/fail, tokens, latency. Compare to
   reports/sales-turn-analysis-eval-2026-09-04.json. Shape failures that
   look like one-key wrapping should now pass via the provider unwrap;
   if they still fail, report them — do not relax fixtures.
3. There was no saved live report for sales_response_generation; produce
   one under reports/ if a live run is possible.

Before editing, list the exact files you will touch. At handoff: changed
files, commands, pass/fail, sources skipped for licence reasons, cards
still unapproved. Do not run git push. Do not approve cards.
```
