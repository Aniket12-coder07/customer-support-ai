"""
Customer Support Automation API
FastAPI server exposing the classifier as a REST API.
"""

from __future__ import annotations
import os
import time
import uuid
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import anthropic

# ─── Import classifier core ──────────────────────────────────────────────────
from classifier import Ticket, process_tickets, SAMPLE_TICKETS, Priority

# ─── App setup ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Customer Support AI API",
    description="AI-powered ticket classification and response generation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Request / Response schemas ───────────────────────────────────────────────

class TicketRequest(BaseModel):
    subject: str
    body: str
    customer_name: str
    customer_email: str

class TicketResponse(BaseModel):
    ticket_id: str
    category: str
    priority: str
    sentiment: str
    confidence: float
    key_issues: List[str]
    suggested_response: str
    escalate: bool
    reasoning: str
    processing_time_ms: int

class BatchRequest(BaseModel):
    tickets: List[TicketRequest]

class BatchResponse(BaseModel):
    processed: int
    results: List[TicketResponse]
    summary: dict

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "service": "Customer Support AI", "version": "1.0.0"}

@app.get("/health", tags=["health"])
async def health():
    return {"status": "healthy", "timestamp": time.time()}

@app.post("/classify", response_model=TicketResponse, tags=["classify"])
async def classify_single(
    req: TicketRequest,
    x_api_key: Optional[str] = Header(default=None),
):
    """Classify a single support ticket."""
    api_key = x_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    t0 = time.time()
    ticket = Ticket(
        id=str(uuid.uuid4())[:8].upper(),
        subject=req.subject,
        body=req.body,
        customer_name=req.customer_name,
        customer_email=req.customer_email,
    )

    results = process_tickets([ticket], api_key=api_key)
    if not results:
        raise HTTPException(status_code=500, detail="Classification failed")

    r = results[0]
    elapsed = int((time.time() - t0) * 1000)

    return TicketResponse(
        ticket_id=r.ticket_id,
        category=r.category,
        priority=r.priority,
        sentiment=r.sentiment,
        confidence=r.confidence,
        key_issues=r.key_issues,
        suggested_response=r.suggested_response,
        escalate=r.escalate,
        reasoning=r.reasoning,
        processing_time_ms=elapsed,
    )

@app.post("/classify/batch", response_model=BatchResponse, tags=["classify"])
async def classify_batch(
    req: BatchRequest,
    x_api_key: Optional[str] = Header(default=None),
):
    """Classify a batch of support tickets."""
    api_key = x_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    if len(req.tickets) > 20:
        raise HTTPException(status_code=400, detail="Max 20 tickets per batch")

    tickets = [
        Ticket(
            id=str(uuid.uuid4())[:8].upper(),
            subject=t.subject,
            body=t.body,
            customer_name=t.customer_name,
            customer_email=t.customer_email,
        )
        for t in req.tickets
    ]

    results = process_tickets(tickets, api_key=api_key)

    priority_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    escalations = 0

    responses = []
    for r in results:
        priority_counts[r.priority] = priority_counts.get(r.priority, 0) + 1
        category_counts[r.category] = category_counts.get(r.category, 0) + 1
        if r.escalate:
            escalations += 1
        responses.append(TicketResponse(
            ticket_id=r.ticket_id,
            category=r.category,
            priority=r.priority,
            sentiment=r.sentiment,
            confidence=r.confidence,
            key_issues=r.key_issues,
            suggested_response=r.suggested_response,
            escalate=r.escalate,
            reasoning=r.reasoning,
            processing_time_ms=0,
        ))

    return BatchResponse(
        processed=len(results),
        results=responses,
        summary={
            "by_priority": priority_counts,
            "by_category": category_counts,
            "escalations_needed": escalations,
        },
    )

@app.get("/demo", response_model=BatchResponse, tags=["demo"])
async def run_demo(x_api_key: Optional[str] = Header(default=None)):
    """Run the classifier on built-in sample tickets."""
    api_key = x_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    results = process_tickets(SAMPLE_TICKETS, api_key=api_key)

    priority_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    escalations = 0
    responses = []

    for r in results:
        priority_counts[r.priority] = priority_counts.get(r.priority, 0) + 1
        category_counts[r.category] = category_counts.get(r.category, 0) + 1
        if r.escalate:
            escalations += 1
        responses.append(TicketResponse(
            ticket_id=r.ticket_id,
            category=r.category,
            priority=r.priority,
            sentiment=r.sentiment,
            confidence=r.confidence,
            key_issues=r.key_issues,
            suggested_response=r.suggested_response,
            escalate=r.escalate,
            reasoning=r.reasoning,
            processing_time_ms=0,
        ))

    return BatchResponse(
        processed=len(results),
        results=responses,
        summary={
            "by_priority": priority_counts,
            "by_category": category_counts,
            "escalations_needed": escalations,
        },
    )

# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
