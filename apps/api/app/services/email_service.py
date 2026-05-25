"""
Email Service — sends transactional emails via Resend REST API.
Silently no-ops if RESEND_API_KEY is not configured or EMAIL_ENABLED is False.
"""
import logging
import httpx
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_SEND_URL = "https://api.resend.com/emails"


def _email_available() -> bool:
    return bool(settings.RESEND_API_KEY and settings.EMAIL_ENABLED)


async def _send(to: str, subject: str, html: str) -> bool:
    """POST to Resend API. Returns True on success, False on failure."""
    if not _email_available():
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                RESEND_SEND_URL,
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": settings.EMAIL_FROM,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
            if resp.status_code in (200, 201):
                logger.info(f"Email sent to {to}: {subject}")
                return True
            else:
                logger.warning(f"Resend returned {resp.status_code}: {resp.text[:200]}")
                return False
    except Exception as e:
        logger.warning(f"Email send failed: {e}")
        return False


def _score_color(score: float) -> str:
    if score >= 85:
        return "#10b981"
    if score >= 70:
        return "#f59e0b"
    if score >= 50:
        return "#ef4444"
    return "#991b1b"


def _base_email(body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr><td style="background:#1e3a5f;padding:24px 32px;">
          <p style="margin:0;color:#ffffff;font-size:20px;font-weight:700;letter-spacing:-0.5px;">Clyira</p>
          <p style="margin:4px 0 0;color:#94a3b8;font-size:12px;">Quality Intelligence Platform</p>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:32px;">
          {body_html}
        </td></tr>
        <!-- Footer -->
        <tr><td style="padding:20px 32px;background:#f8fafc;border-top:1px solid #e2e8f0;">
          <p style="margin:0;color:#94a3b8;font-size:11px;text-align:center;">
            You're receiving this because you have an active Clyira account.<br>
            <a href="https://clyira-platform-web.vercel.app/settings" style="color:#1e3a5f;">Manage notification settings</a>
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


async def send_assessment_complete(
    to: str,
    doc_title: str,
    score: float,
    score_band: str,
    findings_critical: int,
    findings_high: int,
    assessment_id: str,
    document_id: str,
) -> None:
    """Send assessment completion email."""
    score_col = _score_color(score)
    di_warning = ""
    if score <= 50 and findings_critical > 0:
        di_warning = f"""<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 16px;margin:16px 0;">
          <p style="margin:0;color:#991b1b;font-size:13px;font-weight:600;">⚠️ Data Integrity Hold Active — score capped at 50</p>
        </div>"""

    body = f"""
<h2 style="margin:0 0 8px;color:#1e293b;font-size:18px;font-weight:700;">Assessment Complete</h2>
<p style="margin:0 0 24px;color:#64748b;font-size:14px;">{doc_title}</p>

<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
  <tr>
    <td style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:20px;text-align:center;width:48%;">
      <p style="margin:0;color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Clyira Score</p>
      <p style="margin:8px 0 4px;font-size:40px;font-weight:800;color:{score_col};">{score:.1f}</p>
      <p style="margin:0;color:#94a3b8;font-size:12px;">{score_band}</p>
    </td>
    <td width="4%"></td>
    <td style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:20px;text-align:center;width:48%;">
      <p style="margin:0;color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Findings</p>
      <p style="margin:8px 0 4px;font-size:14px;color:#1e293b;">
        {'<span style="color:#ef4444;font-weight:700;">' + str(findings_critical) + ' Critical</span>' if findings_critical else ''}
        {'&nbsp;&nbsp;' if findings_critical and findings_high else ''}
        {'<span style="color:#f59e0b;font-weight:700;">' + str(findings_high) + ' High</span>' if findings_high else ''}
        {'<span style="color:#10b981;font-weight:600;">No critical or high</span>' if not findings_critical and not findings_high else ''}
      </p>
    </td>
  </tr>
</table>

{di_warning}

<a href="https://clyira-platform-web.vercel.app/documents/{document_id}"
   style="display:inline-block;background:#1e3a5f;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;">
  View Assessment →
</a>"""

    await _send(
        to=to,
        subject=f"Assessment Complete: {doc_title} — {score:.0f} / 100",
        html=_base_email(body),
    )


async def send_di_hold_alert(
    to: str,
    doc_title: str,
    document_id: str,
    reason: Optional[str] = None,
) -> None:
    """Send data integrity hold alert email."""
    reason_block = f'<p style="margin:0 0 20px;color:#64748b;font-size:14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:12px 16px;"><strong>Reason:</strong> {reason}</p>' if reason else ""

    body = f"""
<div style="background:#fef2f2;border:2px solid #ef4444;border-radius:10px;padding:16px 20px;margin-bottom:24px;">
  <p style="margin:0;color:#991b1b;font-size:15px;font-weight:700;">⛔ Data Integrity Hold Activated</p>
</div>

<p style="margin:0 0 8px;color:#1e293b;font-size:15px;font-weight:600;">{doc_title}</p>
<p style="margin:0 0 20px;color:#64748b;font-size:14px;">A Data Integrity hold has been placed on this document. The Clyira Score has been capped at 50 until the hold is resolved.</p>

{reason_block}

<p style="margin:0 0 20px;color:#64748b;font-size:13px;">
  Data Integrity holds are triggered when ALCOA+ violations (L4 critical findings) are detected in the document,
  indicating potential issues with data completeness, accuracy, or auditability under 21 CFR Part 211.
</p>

<a href="https://clyira-platform-web.vercel.app/documents/{document_id}"
   style="display:inline-block;background:#991b1b;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;">
  Review Document →
</a>"""

    await _send(
        to=to,
        subject=f"⚠️ Data Integrity Hold: {doc_title}",
        html=_base_email(body),
    )


async def send_bulk_assessment_complete(
    to: str,
    docs_assessed: int,
    docs_failed: int,
    company_score: Optional[float],
) -> None:
    """Send bulk assessment completion summary email."""
    score_block = ""
    if company_score is not None:
        score_col = _score_color(company_score)
        score_block = f"""<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:20px;text-align:center;margin:16px 0;">
  <p style="margin:0;color:#64748b;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Updated Company Readiness Score</p>
  <p style="margin:8px 0 0;font-size:42px;font-weight:800;color:{score_col};">{company_score:.1f}</p>
</div>"""

    body = f"""
<h2 style="margin:0 0 8px;color:#1e293b;font-size:18px;font-weight:700;">Bulk Assessment Complete</h2>
<p style="margin:0 0 24px;color:#64748b;font-size:14px;">All documents have been processed by the L1–L11 assessment engine.</p>

<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:16px;">
  <tr>
    <td style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:16px;text-align:center;width:48%;">
      <p style="margin:0;color:#166534;font-size:28px;font-weight:800;">{docs_assessed}</p>
      <p style="margin:4px 0 0;color:#166534;font-size:12px;font-weight:600;">Documents Assessed</p>
    </td>
    <td width="4%"></td>
    <td style="background:{'#fef2f2' if docs_failed else '#f8fafc'};border:1px solid {'#fecaca' if docs_failed else '#e2e8f0'};border-radius:10px;padding:16px;text-align:center;width:48%;">
      <p style="margin:0;color:{'#991b1b' if docs_failed else '#64748b'};font-size:28px;font-weight:800;">{docs_failed}</p>
      <p style="margin:4px 0 0;color:{'#991b1b' if docs_failed else '#64748b'};font-size:12px;font-weight:600;">Failed</p>
    </td>
  </tr>
</table>

{score_block}

<a href="https://clyira-platform-web.vercel.app/dashboard"
   style="display:inline-block;background:#1e3a5f;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;">
  View Dashboard →
</a>"""

    await _send(
        to=to,
        subject=f"Bulk Assessment Complete — {docs_assessed} document{'s' if docs_assessed != 1 else ''} assessed",
        html=_base_email(body),
    )
