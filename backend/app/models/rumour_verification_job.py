"""An in-flight run of the n8n rumour-verification workflow.

n8n Cloud sits behind Cloudflare, which cuts any HTTP request after ~100s
(HTTP 524), and the workflow routinely takes several minutes. So the
backend can't hold one request open for the answer: it starts the workflow,
returns this job's id at once, and n8n POSTs the finished result back to
/rumour-verification/jobs/{id}/result. The client polls the job until it is
`completed` or `failed`.

`callback_token_hash` is the SHA-256 of a random per-job token sent to n8n
with the request; the callback must present the token itself, so nobody
who merely knows a job id can write a result into it.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

JOB_PENDING = "pending"
JOB_COMPLETED = "completed"
JOB_FAILED = "failed"


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RumourVerificationJob(Base):
    __tablename__ = "rumour_verification_job"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JOB_PENDING)

    rumour_text: Mapped[str] = mapped_column(Text, nullable=False)
    rumour_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    log_event: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    callback_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # the RumourVerificationOut the client gets, once completed
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
