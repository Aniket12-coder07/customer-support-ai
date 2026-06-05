"""
AI-Powered Customer Support Automation - Core Classifier
Uses Claude API for ticket classification, sentiment analysis, and response generation.
"""

import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import anthropic

# ─────────────────────────────────────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────────────────────────────────────

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"

class Category(str, Enum):
    BILLING      = "billing"
    TECHNICAL    = "technical"
    ACCOUNT      = "account"
    SHIPPING     = "shipping"
    GENERAL      = "general"
    COMPLAINT    = "complaint"
    FEATURE_REQ  = "feature_request"

@dataclass
class Ticket:
    id: str
    subject: str
    body: str
    customer_name: str
    customer_email: str

@dataclass
class ClassificationResult:
    ticket_id: str
    category: Category
    priority: Priority
    sentiment: str          # positive / neutral / negative / frustrated
    confidence: float       # 0.0 – 1.0
    key_issues: list[str]
    suggested_response: str
    escalate: bool
    reasoning: str

# ─────────────────────────────────────────────────────────────────────────────
# Classifier
# ─────────────────────────────────────────────────────────────────────────────

CLASSIFICATION_PROMPT = """You are a customer-support AI assistant.

Analyze the support ticket below and return a JSON object with EXACTLY these fields:
{
  "category": one of ["billing","technical","account","shipping","general","complaint","feature_request"],
  "priority": one of ["critical","high","medium","low"],
  "sentiment": one of ["positive","neutral","negative","frustrated"],
  "confidence": float 0.0-1.0,
  "key_issues": [list of up to 3 short strings],
  "suggested_response": "A professional, empathetic draft reply (2-4 sentences)",
  "escalate": true if human escalation is needed else false,
  "reasoning": "One sentence explanation of your classification"
}

Priority rules:
- critical: service down, data loss, security breach, or very angry customer
- high: major feature broken, billing error, account locked
- medium: general questions, minor issues
- low: feature requests, compliments, general feedback

Return ONLY the JSON object, no markdown fences, no other text.

TICKET:
Subject: {subject}
From: {customer_name} <{customer_email}>
---
{body}
"""

def classify_ticket(ticket: Ticket, client: anthropic.Anthropic) -> ClassificationResult:
    """Classify a single support ticket using Claude."""
    prompt = CLASSIFICATION_PROMPT.format(
        subject=ticket.subject,
        customer_name=ticket.customer_name,
        customer_email=ticket.customer_email,
        body=ticket.body,
    )

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    data = json.loads(raw)

    return ClassificationResult(
        ticket_id=ticket.id,
        category=Category(data["category"]),
        priority=Priority(data["priority"]),
        sentiment=data["sentiment"],
        confidence=float(data["confidence"]),
        key_issues=data["key_issues"],
        suggested_response=data["suggested_response"],
        escalate=bool(data["escalate"]),
        reasoning=data["reasoning"],
    )

# ─────────────────────────────────────────────────────────────────────────────
# Batch processor
# ─────────────────────────────────────────────────────────────────────────────

def process_tickets(tickets: list[Ticket], api_key: Optional[str] = None) -> list[ClassificationResult]:
    """Process a batch of tickets and return results sorted by priority."""
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}

    results = []
    for ticket in tickets:
        try:
            result = classify_ticket(ticket, client)
            results.append(result)
            print(f"  ✓ [{result.priority.upper()}] {ticket.id} → {result.category}")
        except Exception as e:
            print(f"  ✗ {ticket.id} failed: {e}")

    results.sort(key=lambda r: priority_order[r.priority])
    return results

# ─────────────────────────────────────────────────────────────────────────────
# Demo dataset
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_TICKETS = [
    Ticket(
        id="TKT-001",
        subject="URGENT: Cannot access my account - paid subscription",
        body="I've been locked out of my account for 3 hours. I have a paid Pro subscription and I have a critical demo in 2 hours. Password reset emails are not arriving. This is completely unacceptable!",
        customer_name="Sarah Johnson",
        customer_email="sarah.j@acmecorp.com",
    ),
    Ticket(
        id="TKT-002",
        subject="Question about invoice #INV-2024-887",
        body="Hi team, I noticed I was charged twice for my subscription this month. The amounts are $49.99 on Jan 5 and again on Jan 7. Could you please look into this and issue a refund for the duplicate charge? Thanks!",
        customer_name="Michael Chen",
        customer_email="m.chen@startup.io",
    ),
    Ticket(
        id="TKT-003",
        subject="Feature request: Dark mode",
        body="Love the product! Would be great to have a dark mode option. Especially useful when working late nights. Keep up the great work!",
        customer_name="Alex Rivera",
        customer_email="alex@freelance.dev",
    ),
    Ticket(
        id="TKT-004",
        subject="API returning 500 errors intermittently",
        body="Since yesterday's deployment our integration has been getting sporadic 500 errors from your /v2/process endpoint. Error rate is about 15%. Our error logs show: InternalServerError at timestamp 1705432800. Affecting ~200 of our users.",
        customer_name="DevOps Team",
        customer_email="devops@bigclient.com",
    ),
    Ticket(
        id="TKT-005",
        subject="How do I export my data?",
        body="Hi, I'd like to export all my data as a CSV file. I looked through the settings but couldn't find the option. Is this possible? Thanks",
        customer_name="Emma Wilson",
        customer_email="ewilson@personal.com",
    ),
]

# ─────────────────────────────────────────────────────────────────────────────
# Entry point (for CLI testing)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Customer Support AI Classifier")
    print("=" * 50)
    print(f"Processing {len(SAMPLE_TICKETS)} tickets...\n")

    results = process_tickets(SAMPLE_TICKETS)

    print("\n📊 Results Summary")
    print("=" * 50)
    for r in results:
        escalation = "🚨 ESCALATE" if r.escalate else "✅ Auto"
        print(f"\n[{r.priority.upper()}] {r.ticket_id} | {r.category} | {r.sentiment}")
        print(f"  Issues: {', '.join(r.key_issues)}")
        print(f"  Action: {escalation}")
        print(f"  Draft:  {r.suggested_response[:100]}...")
