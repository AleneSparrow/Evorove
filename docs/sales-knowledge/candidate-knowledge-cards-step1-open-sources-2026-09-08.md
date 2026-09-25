# Candidate cards from open/government sources — 2026-09-08

**Status:** candidate / unapproved / version 0. Do not import. Do not approve.  
Companion Step 1. Cycle 2 mouth only.

Existing 2026-09-04 cards stay candidates. Alignment with spec 0.4 is already in that file. This file only adds cards whose licence is government PD or 1923 U.S. public domain, still **title-only** (no page-checked private copy).

```json
[
  {
    "knowledge_id": "candidate-step1-ftc-no-unsubstantiated-claims-009",
    "version": 0,
    "status": "candidate",
    "source": {
      "title": "Advertising and marketing (FTC business guidance hub)",
      "author": "U.S. Federal Trade Commission",
      "location": "https://www.ftc.gov/business-guidance/advertising-and-marketing",
      "concept": "Advertising claims must be truthful and substantiated",
      "provenance_confidence": "title-only; hub URL, not a page-checked PDF"
    },
    "principle": "Do not state a price, discount, performance result, or guarantee unless that exact claim already exists as an allowed business fact. Puffery and invented proof are out.",
    "applicable_when": ["PRESENT_RELEVANT_VALUE", "ANSWER_OBJECTION", "ASK_FOR_COMMITMENT"],
    "prohibited_when": ["no matching business_fact_id for the claim"],
    "required_sequence": ["use_only_allowed_facts"],
    "forbidden_actions": ["inventing a discount", "promising an outcome the DNA does not state", "citing a statistic that is not a supplied fact"],
    "approved_examples": ["If the listed fact is a free consult, say that consult is free — nothing extra."],
    "posture_0_4": "aligned"
  },
  {
    "knowledge_id": "candidate-step1-fcc-stop-revokes-consent-010",
    "version": 0,
    "status": "candidate",
    "source": {
      "title": "Stop Unwanted Robocalls and Texts",
      "author": "U.S. Federal Communications Commission",
      "location": "https://www.fcc.gov/consumers/guides/stop-unwanted-robocalls-and-texts",
      "concept": "Consumer may revoke consent; STOP ends further marketing texts",
      "provenance_confidence": "title-only; consumer guide URL"
    },
    "principle": "If the person says STOP or otherwise revokes consent, the companion phrases an already-approved end/handoff. It does not keep pitching, ask a discovery question, or offer slots.",
    "applicable_when": ["customer_message contains STOP or clear opt-out"],
    "prohibited_when": ["any continuing sales move after opt-out language"],
    "required_sequence": ["recognize_opt_out", "do_not_continue_the_sale"],
    "forbidden_actions": ["nurture after STOP", "booking after STOP", "Feel-Felt-Found after STOP"],
    "approved_examples": ["You have been unsubscribed and won't hear from us again about this."],
    "posture_0_4": "aligned — STOP is safety/consent, not an objection to argue"
  },
  {
    "knowledge_id": "candidate-step1-hopkins-specific-claims-011",
    "version": 0,
    "status": "candidate",
    "source": {
      "title": "Scientific Advertising",
      "author": "Claude C. Hopkins",
      "location": "https://archive.org/details/scientificadvert0000hopk",
      "concept": "Specific, testable selling claims beat vague boast",
      "provenance_confidence": "title-only; 1923 U.S. public domain; copy not deposited in this repo"
    },
    "principle": "Prefer one concrete, already-allowed fact over a sweeping claim. Do not invent a test result, a typical savings figure, or a ‘everyone finds’ story.",
    "applicable_when": ["PRESENT_RELEVANT_VALUE"],
    "prohibited_when": ["the only available wording would require an unsupplied number or guarantee"],
    "required_sequence": ["name_the_allowed_fact", "tie_it_to_the_customers_stated_problem"],
    "forbidden_actions": ["generic superlatives with no DNA fact", "fake scarcity", "Feel-Felt-Found"],
    "approved_examples": ["You said leads go cold — follow-up goes out in minutes, which is the listed fact for that problem."],
    "posture_0_4": "aligned; pages not verified"
  }
]
```

Owner still reviews before any Settings approve.
