from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


BasisType = Literal[
    "regulatory",
    "industry_guideline",
    "academic",
    "own_policy",
    "illustrative_assumption",
]
VerificationStatus = Literal["verified", "unverified", "needs_review"]
FinalTierImpact = Literal[
    "direct_capacity",
    "direct_stated_tier",
    "indirect_allocation",
    "no_direct_tier_effect",
]


class EvidenceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    config_file: str
    constant_name: str
    value: int | float
    human_description: str
    basis_type: BasisType
    source_citation: str
    source_url: str
    retrieved_date: str
    verification_status: VerificationStatus
    notes: str
    suggested_search_queries: list[str] = Field(min_length=2, max_length=3)
    final_tier_impact: FinalTierImpact


class EvidenceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    entries: list[EvidenceEntry]
