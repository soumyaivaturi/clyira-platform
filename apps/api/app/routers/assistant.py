"""
Author Assistant + QA Assistant endpoints.
Author: Given a finding, draft replacement text for the flagged section.
QA:     Answer questions about a document in the context of GMP/regulatory compliance.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.dtap import DTAPRegistry
from app.models.document import Document
from app.models.assessment import Assessment, Finding
from app.models.user import User

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class AuthorRequest(BaseModel):
    document_id: str
    finding_id: str
    context_hint: Optional[str] = ""  # optional extra instruction from user


class AuthorResponse(BaseModel):
    finding_id: str
    finding_title: str
    draft_text: str
    instruction: str


class QARequest(BaseModel):
    document_id: str
    question: str
    assessment_id: Optional[str] = None  # include findings context if provided


class QAResponse(BaseModel):
    question: str
    answer: str
    citations: list[str] = []


class FindingChatRequest(BaseModel):
    document_id: str
    finding_id: str
    message: str
    history: list[dict] = []  # [{role: "user"|"assistant", content: str}]


class FindingChatResponse(BaseModel):
    reply: str


async def _call_llm_simple(system: str, user: str) -> str:
    """Route to available LLM for assistant calls."""
    from app.engines.llm_engine import _call_llm
    return await _call_llm(system, user)


@router.post("/author", response_model=AuthorResponse)
@limiter.limit("30/minute")
async def draft_fix(
    request: Request,
    data: AuthorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Author Assistant — Given an assessment finding, draft replacement text
    for the section of the document that triggered the finding.
    """
    doc_result = await db.execute(
        select(Document).where(
            Document.id == data.document_id,
            Document.company_id == current_user.company_id,
        )
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Enforce editable/locked mode — locked documents cannot receive suggestion_draft
    if doc.document_category:
        dtap_profile = DTAPRegistry.get_by_category(doc.document_category)
        if dtap_profile and dtap_profile.mode == "locked":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{dtap_profile.display_name} is a locked document type. "
                    "Locked documents record what happened and cannot be edited retroactively. "
                    "Use the Next Steps Action Plan workflow instead."
                ),
            )

    # Scope finding to company via its parent assessment
    finding_result = await db.execute(
        select(Finding)
        .join(Assessment, Assessment.id == Finding.assessment_id)
        .where(
            Finding.id == data.finding_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    finding = finding_result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    # Build the author prompt
    doc_excerpt = ""
    if finding.location and doc.extracted_sections:
        doc_excerpt = doc.extracted_sections.get(finding.location, "")
    if not doc_excerpt and doc.extracted_text:
        # Find ±500 chars around the evidence if present
        if finding.evidence and finding.evidence in doc.extracted_text:
            idx = doc.extracted_text.index(finding.evidence)
            doc_excerpt = doc.extracted_text[max(0, idx - 200): idx + 500]
        else:
            doc_excerpt = doc.extracted_text[:3000]

    system_prompt = """You are Clyira's Author Assistant — an expert pharmaceutical technical writer with deep knowledge of FDA and EMA GMP requirements.

Your task: Given an assessment finding, draft corrected or improved document text that resolves the finding.

REQUIREMENTS:
- Write in formal regulatory document style (active voice, precise language, no ambiguity)
- Replace "should" with "shall" for mandatory requirements
- Include specific references to CFR/ICH where appropriate
- Make the draft complete and directly usable (not a template with [placeholder] fields)
- Keep it concise — only draft what's needed to fix the finding

OUTPUT: Return ONLY the draft text, no preamble, no explanation, no markdown headers."""

    user_prompt = f"""Document: {doc.title} ({doc.document_category})
Finding: [{finding.level}] {finding.severity.upper()} — {finding.title}
Description: {finding.description}
Location: {finding.location or "unknown section"}
Regulatory citation: {finding.regulatory_citation or "N/A"}
{f"Additional instruction: {data.context_hint}" if data.context_hint else ""}

Current document text (relevant excerpt):
{doc_excerpt or "[section not found]"}

Draft replacement/addition text that resolves this finding:"""

    try:
        draft = await _call_llm_simple(system_prompt, user_prompt)
        instruction = (
            f"Replace/update the text in section '{finding.location}' with the draft above. "
            f"Ensure it addresses: {finding.regulatory_citation or 'the identified gap'}."
        )
        return AuthorResponse(
            finding_id=data.finding_id,
            finding_title=finding.title,
            draft_text=draft.strip(),
            instruction=instruction,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM unavailable: {e}",
        )


@router.post("/qa", response_model=QAResponse)
async def qa_document(
    data: QARequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    QA Assistant — Answer GMP/regulatory questions about a specific document.
    Optionally includes assessment findings as context for more informed answers.
    """
    doc_result = await db.execute(
        select(Document).where(
            Document.id == data.document_id,
            Document.company_id == current_user.company_id,
        )
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Include top findings as context if assessment is provided
    findings_context = ""
    if data.assessment_id:
        findings_result = await db.execute(
            select(Finding)
            .where(Finding.assessment_id == data.assessment_id)
            .order_by(Finding.severity)
            .limit(10)
        )
        top_findings = findings_result.scalars().all()
        if top_findings:
            lines = [f"- [{f.level}] {f.severity.upper()}: {f.title}" for f in top_findings]
            findings_context = "\n\nKnown assessment findings for this document:\n" + "\n".join(lines)

    system_prompt = f"""You are Clyira's QA Assistant — a senior GMP compliance expert and regulatory affairs specialist.

You are answering a question about a specific pharmaceutical quality document.
Be concise, accurate, and cite specific regulatory requirements (21 CFR, ICH, EU GMP) when relevant.
If the question cannot be answered from the document content, say so clearly rather than hallucinating.

Document: {doc.title} ({doc.document_category or "unknown category"})"""

    user_prompt = f"""Document content (first 12,000 characters):
{(doc.extracted_text or "")[:12000]}
{findings_context}

Question: {data.question}

Provide a direct, expert answer with regulatory citations where applicable. If citing findings, reference them by level and title."""

    try:
        answer = await _call_llm_simple(system_prompt, user_prompt)

        # Extract any CFR/ICH citations from the answer for the citations field
        import re
        citations = list(set(re.findall(
            r'(?:21 CFR \d+\.\d+|ICH [QES]\d+[a-zA-Z0-9()*]*|EU GMP (?:Annex \d+|Part [I]+)|USP [<\d>]+)',
            answer,
        )))

        return QAResponse(
            question=data.question,
            answer=answer.strip(),
            citations=citations[:10],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM unavailable: {e}",
        )


@router.post("/finding-chat", response_model=FindingChatResponse)
@limiter.limit("30/minute")
async def finding_chat(
    request: Request,
    data: FindingChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Finding Chat — Conversational AI scoped to a single finding.
    Lets users challenge a finding, ask for alternative fixes, understand
    the regulatory basis, or request alternative phrasings.
    """
    doc_result = await db.execute(
        select(Document).where(
            Document.id == data.document_id,
            Document.company_id == current_user.company_id,
        )
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Scope finding to company via its parent assessment
    finding_result = await db.execute(
        select(Finding)
        .join(Assessment, Assessment.id == Finding.assessment_id)
        .where(
            Finding.id == data.finding_id,
            Assessment.company_id == current_user.company_id,
        )
    )
    finding = finding_result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    history_str = ""
    for turn in data.history[-6:]:
        role = "User" if turn.get("role") == "user" else "Assistant"
        history_str += f"\n{role}: {turn.get('content', '')}"

    system_prompt = """You are Clyira's Finding AI — a senior GMP compliance expert and regulatory affairs specialist.

You are in a focused conversation about a single assessment finding in a pharmaceutical quality document.
Your role:
- Answer questions about why the finding was raised
- Explain the specific regulatory requirement that was violated
- Offer alternative fix phrasings if asked
- Challenge your own finding honestly if the user presents valid context (e.g., criteria exist in another document)
- Suggest when a finding should be disputed vs. acknowledged vs. resolved
- Reference specific Warning Letter patterns or 483 observations when relevant
- Be concise and direct — this is a working conversation, not a report

If the user provides context that changes the assessment (e.g., "the criteria are in a separate spec doc"), acknowledge this and suggest the appropriate action (dispute, cross-reference, etc.)."""

    user_prompt = f"""Document: {doc.title} ({doc.document_category or "unknown"})

Finding context:
  Severity: {finding.severity.upper()}
  Level: {finding.level} — {finding.level_name or ""}
  Title: {finding.title}
  Description: {finding.description}
  Evidence: {finding.evidence or "N/A"}
  Location: {finding.location or "N/A"}
  Regulatory citation: {finding.regulatory_citation or "N/A"}
{f"  Suggested fix: {finding.suggestion_draft}" if finding.suggestion_draft else ""}

Conversation so far:{history_str if history_str else " (new conversation)"}

User: {data.message}

Provide a direct, expert response. If suggesting alternative text, format it clearly. Keep response under 200 words."""

    try:
        reply = await _call_llm_simple(system_prompt, user_prompt)
        return FindingChatResponse(reply=reply.strip())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM unavailable: {e}",
        )
