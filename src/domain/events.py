"""Event names used in process-case audit history."""

from enum import StrEnum


class EventType(StrEnum):
    LEAD_INTAKE_RECEIVED = "LEAD_INTAKE_RECEIVED"
    INTENT_EXTRACTED = "INTENT_EXTRACTED"
    QUALIFICATION_EVALUATED = "QUALIFICATION_EVALUATED"
    CUSTOMER_RESPONSE_CREATED = "CUSTOMER_RESPONSE_CREATED"
    TRIGGER_RECEIVED = "TRIGGER_RECEIVED"
    DECISION_RECORDED = "DECISION_RECORDED"
    STATE_CHANGED = "STATE_CHANGED"
    TRANSITION_REJECTED = "TRANSITION_REJECTED"
    DUPLICATE_IGNORED = "DUPLICATE_IGNORED"
    COMMERCIAL_PATH_SELECTED = "COMMERCIAL_PATH_SELECTED"
    AVAILABILITY_CALCULATED = "AVAILABILITY_CALCULATED"
    SLOTS_PROPOSED = "SLOTS_PROPOSED"
    SLOT_SELECTED = "SLOT_SELECTED"
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_RESCHEDULED = "BOOKING_RESCHEDULED"
    PRICING_INPUT_RECORDED = "PRICING_INPUT_RECORDED"
    QUOTE_CALCULATED = "QUOTE_CALCULATED"
    QUOTE_PRESENTED = "QUOTE_PRESENTED"
    QUOTE_ACCEPTED = "QUOTE_ACCEPTED"
    QUOTE_REJECTED = "QUOTE_REJECTED"
    QUOTE_EXPIRED = "QUOTE_EXPIRED"
    PAYMENT_REQUEST_CREATED = "PAYMENT_REQUEST_CREATED"
    PAYMENT_REQUEST_EXPIRED = "PAYMENT_REQUEST_EXPIRED"
    HUMAN_REPLY_SENT = "HUMAN_REPLY_SENT"
    ESCALATION_FEEDBACK_RECORDED = "ESCALATION_FEEDBACK_RECORDED"
    # Proactive re-contact of a stalled lead (universal-sales-cycle-model.md
    # section 8) -- recorded by PersistentFollowUpRunner, never by the
    # reactive LeadIntakeService.receive() path.
    FOLLOW_UP_SENT = "FOLLOW_UP_SENT"
    # Customer asked to continue later. This is the engine's own follow-up
    # in the same channel, not a staff phone call and not a CRM record.
    # Recorded by SalesLiveTurnService when it executes SCHEDULE_CALLBACK.
    CALLBACK_REQUESTED = "CALLBACK_REQUESTED"
    # Outbound sales follow-up after a pause (spec section 13). Distinct from
    # FOLLOW_UP_SENT (stalled pre-QUALIFIED SMS) and from ProcessState.FOLLOW_UP.
    # Does not change ProcessState and does not create a CRM record.
    SALES_FOLLOW_UP_SENT = "SALES_FOLLOW_UP_SENT"
    # Engine asked the business owner for a missing fact. The customer
    # conversation stays with the engine. Not NEEDS_HUMAN and not a CRM task.
    BUSINESS_FACT_REQUESTED = "BUSINESS_FACT_REQUESTED"
    # Owner supplied the missing fact; the engine continued in-channel.
    # Does not change ProcessState and is not a human takeover.
    BUSINESS_FACT_RESUMED = "BUSINESS_FACT_RESUMED"
