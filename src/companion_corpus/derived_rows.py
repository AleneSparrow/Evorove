"""Product-aligned JSONL unlocked when a known title is deposited.

Rows are original Evorove examples, not book quotations. Spec 0.4 applies.
"""

from __future__ import annotations

from copy import deepcopy

from .known_titles import CORE_CATALOG_IDS, KnownTitle

# Analyzer / generator extras keyed by catalog_id.
_ANALYZER: dict[str, list[dict]] = {
    "spin-selling": [
        {
            "id": "an-corpus-spin-problem-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "spin-selling",
            "customer_message": "Leads sit in the inbox overnight and nobody owns the reply",
            "profile_context": {
                "stage": "DISCOVERY",
                "current_problem": None,
                "desired_outcome": None,
            },
            "target": {
                "observed_stage": "DISCOVERY",
                "confidence": 0.82,
                "customer_intent": "Describes an unowned overnight-lead problem",
                "signals": [
                    {
                        "kind": "customer_goal",
                        "value": "Needs ownership of overnight lead replies",
                        "evidence": "nobody owns the reply",
                    }
                ],
                "objections": [],
                "commitment_level": "CURIOUS",
                "recommended_moves": ["ASK_DISCOVERY_QUESTION"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "challenger-sale": [
        {
            "id": "an-corpus-challenger-reframe-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "challenger-sale",
            "customer_message": "We already have a process, people just don't follow it",
            "profile_context": {
                "stage": "PRESENTATION",
                "current_problem": "inconsistent follow-up",
                "desired_outcome": "replies same day",
            },
            "target": {
                "observed_stage": "PRESENTATION",
                "confidence": 0.78,
                "customer_intent": "Blames adherence, not the process itself",
                "signals": [
                    {
                        "kind": "customer_goal",
                        "value": "Wants the existing process actually followed",
                        "evidence": "people just don't follow it",
                    }
                ],
                "objections": [],
                "commitment_level": "INTERESTED",
                "recommended_moves": ["PRESENT_RELEVANT_VALUE"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "never-split-the-difference": [
        {
            "id": "an-corpus-voss-price-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "never-split-the-difference",
            "customer_message": "The number is just too high for us right now",
            "profile_context": {
                "stage": "PRESENTATION",
                "current_problem": "missed leads",
                "desired_outcome": "faster follow-up",
            },
            "target": {
                "observed_stage": "OBJECTION_HANDLING",
                "confidence": 0.86,
                "customer_intent": "Objects to price without naming the cause",
                "signals": [],
                "objections": [
                    {
                        "objection_type": "PRICE",
                        "status": "ACTIVE",
                        "evidence": "too high for us right now",
                        "cause": None,
                    }
                ],
                "commitment_level": "CONSIDERING",
                "recommended_moves": ["DIAGNOSE_OBJECTION"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "fanatical-prospecting": [
        {
            "id": "an-corpus-followup-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "fanatical-prospecting",
            "customer_message": "I got busy. Circle back next week maybe",
            "profile_context": {
                "stage": "FOLLOW_UP",
                "current_problem": "missed leads",
                "desired_outcome": "faster follow-up",
            },
            "target": {
                "observed_stage": "FOLLOW_UP",
                "confidence": 0.8,
                "customer_intent": "Defers without revoking consent",
                "signals": [
                    {
                        "kind": "preferred_contact_time",
                        "value": "Next week",
                        "evidence": "Circle back next week maybe",
                    }
                ],
                "objections": [],
                "commitment_level": "CONSIDERING",
                "recommended_moves": ["SEND_CONTEXTUAL_FOLLOW_UP"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "influence": [
        {
            "id": "an-corpus-influence-think-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "influence",
            "customer_message": "I need to think about it",
            "profile_context": {
                "stage": "COMMITMENT",
                "current_problem": "missed leads",
                "desired_outcome": "faster follow-up",
            },
            "target": {
                "observed_stage": "OBJECTION_HANDLING",
                "confidence": 0.8,
                "customer_intent": "Asks for time; cause of hesitation is not named",
                "signals": [],
                "objections": [
                    {
                        "objection_type": "NEED_TO_THINK",
                        "status": "ACTIVE",
                        "evidence": "need to think about it",
                        "cause": None,
                    }
                ],
                "commitment_level": "CONSIDERING",
                "recommended_moves": ["DIAGNOSE_OBJECTION"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "scientific-advertising": [
        {
            "id": "an-corpus-hopkins-claim-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "scientific-advertising",
            "customer_message": "Can you guarantee I'll get more clients?",
            "profile_context": {
                "stage": "PRESENTATION",
                "current_problem": "missed leads",
                "desired_outcome": "more booked work",
            },
            "target": {
                "observed_stage": "OBJECTION_HANDLING",
                "confidence": 0.84,
                "customer_intent": "Asks for a results guarantee",
                "signals": [],
                "objections": [
                    {
                        "objection_type": "TRUST",
                        "status": "ACTIVE",
                        "evidence": "guarantee I'll get more clients",
                        "cause": None,
                    }
                ],
                "commitment_level": "CONSIDERING",
                "recommended_moves": ["DIAGNOSE_OBJECTION"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "sandler-rules": [
        {
            "id": "an-corpus-sandler-qualify-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "sandler-rules",
            "customer_message": "Just send the overview, we'll figure out if we need it",
            "profile_context": {
                "stage": "DISCOVERY",
                "current_problem": None,
                "desired_outcome": None,
            },
            "target": {
                "observed_stage": "DISCOVERY",
                "confidence": 0.8,
                "customer_intent": "Asks for a pitch before the problem is owned",
                "signals": [
                    {
                        "kind": "buying_signal",
                        "value": "Wants materials instead of a diagnosis",
                        "evidence": "Just send the overview",
                    }
                ],
                "objections": [],
                "commitment_level": "CURIOUS",
                "recommended_moves": ["ASK_DISCOVERY_QUESTION"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "getting-to-yes": [
        {
            "id": "an-corpus-gty-position-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "getting-to-yes",
            "customer_message": "We already have a vendor. Price is the only thing that would make us switch",
            "profile_context": {
                "stage": "PRESENTATION",
                "current_problem": "missed leads",
                "desired_outcome": "faster follow-up",
            },
            "target": {
                "observed_stage": "OBJECTION_HANDLING",
                "confidence": 0.84,
                "customer_intent": "States a bargaining position, not the underlying interest",
                "signals": [],
                "objections": [
                    {
                        "objection_type": "PRICE",
                        "status": "ACTIVE",
                        "evidence": "Price is the only thing",
                        "cause": None,
                    }
                ],
                "commitment_level": "CONSIDERING",
                "recommended_moves": ["DIAGNOSE_OBJECTION"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "selling-to-big-companies": [
        {
            "id": "an-corpus-konrath-gate-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "selling-to-big-companies",
            "customer_message": "I'm slammed. Mail the deck to my assistant",
            "profile_context": {
                "stage": "DISCOVERY",
                "current_problem": "missed leads",
                "desired_outcome": "faster follow-up",
            },
            "target": {
                "observed_stage": "OBJECTION_HANDLING",
                "confidence": 0.82,
                "customer_intent": "Routes the seller away from the person who sees the problem",
                "signals": [],
                "objections": [
                    {
                        "objection_type": "AUTHORITY",
                        "status": "ACTIVE",
                        "evidence": "Mail the deck to my assistant",
                        "cause": None,
                    }
                ],
                "commitment_level": "CURIOUS",
                "recommended_moves": ["DIAGNOSE_OBJECTION"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "agile-selling": [
        {
            "id": "an-corpus-agile-bandwidth-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "agile-selling",
            "customer_message": "We just changed CRMs. I don't have bandwidth for another system",
            "profile_context": {
                "stage": "PRESENTATION",
                "current_problem": "missed leads",
                "desired_outcome": "faster follow-up",
            },
            "target": {
                "observed_stage": "OBJECTION_HANDLING",
                "confidence": 0.83,
                "customer_intent": "Treats the offer as extra work on top of a CRM switch",
                "signals": [],
                "objections": [
                    {
                        "objection_type": "TIMING",
                        "status": "ACTIVE",
                        "evidence": "don't have bandwidth for another system",
                        "cause": None,
                    }
                ],
                "commitment_level": "CONSIDERING",
                "recommended_moves": ["DIAGNOSE_OBJECTION"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "storybrand": [
        {
            "id": "an-corpus-storybrand-hero-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "storybrand",
            "customer_message": "Tell me about your platform and what makes you different",
            "profile_context": {
                "stage": "PRESENTATION",
                "current_problem": "missed leads",
                "desired_outcome": "faster follow-up",
            },
            "target": {
                "observed_stage": "PRESENTATION",
                "confidence": 0.78,
                "customer_intent": "Asks for a company-as-hero pitch",
                "signals": [
                    {
                        "kind": "decision_criteria",
                        "value": "Wants a differentiation story",
                        "evidence": "what makes you different",
                    }
                ],
                "objections": [],
                "commitment_level": "INTERESTED",
                "recommended_moves": ["PRESENT_RELEVANT_VALUE"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "storybrand-2": [
        {
            "id": "an-corpus-storybrand2-confirm-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "storybrand-2",
            "customer_message": "I need something that makes us look professional to clients waiting on a callback",
            "profile_context": {
                "stage": "DISCOVERY",
                "current_problem": "missed leads",
                "desired_outcome": None,
            },
            "target": {
                "observed_stage": "NEEDS_CONFIRMED",
                "confidence": 0.84,
                "customer_intent": "Names how the missed callback looks to their own clients",
                "signals": [
                    {
                        "kind": "desired_outcome",
                        "value": "Look professional while clients wait on a callback",
                        "evidence": "look professional to clients waiting on a callback",
                    }
                ],
                "objections": [],
                "commitment_level": "INTERESTED",
                "recommended_moves": ["CONFIRM_CUSTOMER_NEED"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
    "storybrand-funnel": [
        {
            "id": "an-corpus-funnel-dump-001",
            "task": "analyzer",
            "polarity": "positive",
            "catalog_id": "storybrand-funnel",
            "customer_message": "Can you send everything? Website, cases, pricing, the full pack",
            "profile_context": {
                "stage": "COMMITMENT",
                "current_problem": "missed leads",
                "desired_outcome": "faster follow-up",
            },
            "target": {
                "observed_stage": "COMMITMENT",
                "confidence": 0.8,
                "customer_intent": "Asks for a dump instead of one next step",
                "signals": [
                    {
                        "kind": "buying_signal",
                        "value": "Wants the full pack of materials",
                        "evidence": "send everything",
                    }
                ],
                "objections": [],
                "commitment_level": "CONSIDERING",
                "recommended_moves": ["ASK_FOR_COMMITMENT"],
                "requested_callback_at": None,
                "requires_human": False,
            },
        }
    ],
}

_GENERATOR: dict[str, list[dict]] = {
    "spin-selling": [
        {
            "id": "gen-corpus-spin-discover-001",
            "task": "generator",
            "polarity": "positive",
            "catalog_id": "spin-selling",
            "approved_move": "ASK_DISCOVERY_QUESTION",
            "sales_stage": "DISCOVERY",
            "channel": "sms",
            "customer_message": "Leads sit in the inbox overnight and nobody owns the reply",
            "target": {
                "move": "ASK_DISCOVERY_QUESTION",
                "message_text": "When a lead sits overnight, what usually happens to it by morning?",
                "knowledge_ids": [],
                "business_fact_ids": [],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["\\?\\s*.+\\?"],
        }
    ],
    "challenger-sale": [
        {
            "id": "gen-corpus-challenger-value-001",
            "task": "generator",
            "polarity": "positive",
            "catalog_id": "challenger-sale",
            "approved_move": "PRESENT_RELEVANT_VALUE",
            "sales_stage": "PRESENTATION",
            "channel": "chat",
            "customer_message": "We already have a process, people just don't follow it",
            "allowed_business_fact_ids": ["followup-minutes-001"],
            "target": {
                "move": "PRESENT_RELEVANT_VALUE",
                "message_text": "If the process only lives in people's heads, the listed fact is follow-up in minutes so it happens even when someone skips the checklist.",
                "knowledge_ids": [],
                "business_fact_ids": ["followup-minutes-001"],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["\\bguarantee", "industry average"],
        }
    ],
    "never-split-the-difference": [
        {
            "id": "gen-corpus-voss-diagnose-001",
            "task": "generator",
            "polarity": "positive",
            "catalog_id": "never-split-the-difference",
            "approved_move": "DIAGNOSE_OBJECTION",
            "sales_stage": "OBJECTION_HANDLING",
            "channel": "chat",
            "customer_message": "The number is just too high for us right now",
            "target": {
                "move": "DIAGNOSE_OBJECTION",
                "message_text": "Got it — the number landed heavy. What's the part that doesn't fit: cash this month, or whether it would even pay for itself?",
                "knowledge_ids": [],
                "business_fact_ids": [],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": [
                "I understand how you feel",
                "others have felt",
                "what they found",
            ],
        }
    ],
    "fanatical-prospecting": [
        {
            "id": "gen-corpus-followup-001",
            "task": "generator",
            "polarity": "positive",
            "catalog_id": "fanatical-prospecting",
            "approved_move": "SEND_CONTEXTUAL_FOLLOW_UP",
            "sales_stage": "FOLLOW_UP",
            "channel": "sms",
            "customer_message": "I got busy. Circle back next week maybe",
            "target": {
                "move": "SEND_CONTEXTUAL_FOLLOW_UP",
                "message_text": "I'll leave the overnight-lead thread until next week — ping when you want that reply-ownership piece back on the table.",
                "knowledge_ids": [],
                "business_fact_ids": [],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["last chance", "spots are filling"],
        }
    ],
    "influence": [
        {
            "id": "gen-corpus-influence-neg-scarcity-001",
            "task": "generator",
            "polarity": "negative",
            "catalog_id": "influence",
            "approved_move": "ASK_FOR_COMMITMENT",
            "sales_stage": "COMMITMENT",
            "channel": "chat",
            "customer_message": "I need to think about it",
            "bad_message_text": "Spots are filling up fast, this weekend is probably your last chance.",
            "target": {
                "move": "ASK_FOR_COMMITMENT",
                "message_text": "No fake deadline. Want to sit with it, or pick a consult hour while the missed follow-up is still loud?",
                "knowledge_ids": [],
                "business_fact_ids": [],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["spots are filling", "last chance"],
        }
    ],
    "scientific-advertising": [
        {
            "id": "gen-corpus-hopkins-no-guarantee-001",
            "task": "generator",
            "polarity": "negative",
            "catalog_id": "scientific-advertising",
            "approved_move": "PRESENT_RELEVANT_VALUE",
            "sales_stage": "PRESENTATION",
            "channel": "chat",
            "customer_message": "Can you guarantee I'll get more clients?",
            "bad_message_text": "We guarantee you'll get more clients.",
            "target": {
                "move": "PRESENT_RELEVANT_VALUE",
                "message_text": "I won't promise a client count. The listed fact is follow-up in minutes so fewer leads go cold — that's the piece we can stand behind.",
                "knowledge_ids": [],
                "business_fact_ids": ["followup-minutes-001"],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["\\bguarantee you'll"],
        }
    ],
    "sandler-rules": [
        {
            "id": "gen-corpus-sandler-qualify-001",
            "task": "generator",
            "polarity": "negative",
            "catalog_id": "sandler-rules",
            "approved_move": "ASK_DISCOVERY_QUESTION",
            "sales_stage": "DISCOVERY",
            "channel": "sms",
            "customer_message": "Just send the overview, we'll figure out if we need it",
            "bad_message_text": "Sure — here's the full package, pricing, and a ten-slide overview.",
            "target": {
                "move": "ASK_DISCOVERY_QUESTION",
                "message_text": "Before I dump a pack: when a lead sits overnight, who actually owns the reply?",
                "knowledge_ids": [],
                "business_fact_ids": [],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["full package", "ten-slide", "\\?\\s*.+\\?"],
        }
    ],
    "getting-to-yes": [
        {
            "id": "gen-corpus-gty-interest-001",
            "task": "generator",
            "polarity": "positive",
            "catalog_id": "getting-to-yes",
            "approved_move": "DIAGNOSE_OBJECTION",
            "sales_stage": "OBJECTION_HANDLING",
            "channel": "chat",
            "customer_message": "We already have a vendor. Price is the only thing that would make us switch",
            "target": {
                "move": "DIAGNOSE_OBJECTION",
                "message_text": "Got it — staying put unless the number moves. What's under that: switching cost, or whether overnight leads would even get owned?",
                "knowledge_ids": [],
                "business_fact_ids": [],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["I understand how you feel", "20% off", "\\?\\s*.+\\?"],
        }
    ],
    "selling-to-big-companies": [
        {
            "id": "gen-corpus-konrath-gate-001",
            "task": "generator",
            "polarity": "positive",
            "catalog_id": "selling-to-big-companies",
            "approved_move": "DIAGNOSE_OBJECTION",
            "sales_stage": "OBJECTION_HANDLING",
            "channel": "chat",
            "customer_message": "I'm slammed. Mail the deck to my assistant",
            "target": {
                "move": "DIAGNOSE_OBJECTION",
                "message_text": "I won't dump a deck on your assistant. Who actually sees the overnight leads die — you, or someone else?",
                "knowledge_ids": [],
                "business_fact_ids": [],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["attached deck", "just looping", "\\?\\s*.+\\?"],
        }
    ],
    "agile-selling": [
        {
            "id": "gen-corpus-agile-bandwidth-001",
            "task": "generator",
            "polarity": "positive",
            "catalog_id": "agile-selling",
            "approved_move": "DIAGNOSE_OBJECTION",
            "sales_stage": "OBJECTION_HANDLING",
            "channel": "chat",
            "customer_message": "We just changed CRMs. I don't have bandwidth for another system",
            "target": {
                "move": "DIAGNOSE_OBJECTION",
                "message_text": "A second system on a CRM hangover is a lot. What's eating the bandwidth — the migration, or the overnight replies still slipping?",
                "knowledge_ids": [],
                "business_fact_ids": [],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["easy to learn", "\\bguarantee", "\\?\\s*.+\\?"],
        }
    ],
    "storybrand": [
        {
            "id": "gen-corpus-storybrand-hero-001",
            "task": "generator",
            "polarity": "positive",
            "catalog_id": "storybrand",
            "approved_move": "PRESENT_RELEVANT_VALUE",
            "sales_stage": "PRESENTATION",
            "channel": "chat",
            "customer_message": "Tell me about your platform and what makes you different",
            "allowed_business_fact_ids": ["followup-minutes-001"],
            "target": {
                "move": "PRESENT_RELEVANT_VALUE",
                "message_text": "You're the one whose clients wait overnight. The listed fact is follow-up in minutes so that wait doesn't sit on you.",
                "knowledge_ids": [],
                "business_fact_ids": ["followup-minutes-001"],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["our platform", "what makes us different", "industry leading"],
        }
    ],
    "storybrand-2": [
        {
            "id": "gen-corpus-storybrand2-confirm-001",
            "task": "generator",
            "polarity": "positive",
            "catalog_id": "storybrand-2",
            "approved_move": "CONFIRM_CUSTOMER_NEED",
            "sales_stage": "NEEDS_CONFIRMED",
            "channel": "chat",
            "customer_message": "I need something that makes us look professional to clients waiting on a callback",
            "target": {
                "move": "CONFIRM_CUSTOMER_NEED",
                "message_text": "So the job is looking solid to people already waiting on a callback — not collecting another tool. Did I hear that right?",
                "knowledge_ids": [],
                "business_fact_ids": [],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["\\bguarantee", "our brand story"],
        }
    ],
    "storybrand-funnel": [
        {
            "id": "gen-corpus-funnel-one-step-001",
            "task": "generator",
            "polarity": "negative",
            "catalog_id": "storybrand-funnel",
            "approved_move": "ASK_FOR_COMMITMENT",
            "sales_stage": "COMMITMENT",
            "channel": "chat",
            "customer_message": "Can you send everything? Website, cases, pricing, the full pack",
            "bad_message_text": "Here's the site, three case studies, pricing, and a webinar link.",
            "target": {
                "move": "ASK_FOR_COMMITMENT",
                "message_text": "I won't bury you in a pack. One step: pick a consult hour while the overnight-lead mess is still loud, or sit with it?",
                "knowledge_ids": [],
                "business_fact_ids": [],
                "customer_evidence_ids": ["ev-1"],
                "used_safe_fallback": False,
            },
            "forbidden_patterns": ["case studies", "webinar link", "full pack"],
        }
    ],
}


def rows_for_title(title: KnownTitle) -> tuple[list[dict], list[dict]]:
    from .rulebook import rows_from_rulebook

    if title.catalog_id not in CORE_CATALOG_IDS:
        return [], []
    analyzer = deepcopy(_ANALYZER.get(title.catalog_id, []))
    generator = deepcopy(_GENERATOR.get(title.catalog_id, []))
    extra_a, extra_g = rows_from_rulebook(title.catalog_id)
    analyzer.extend(extra_a)
    generator.extend(extra_g)
    return analyzer, generator
