"""Structured types for the vendor desk agent."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class VendorDecision(BaseModel):
    """What the agent returns for one vendor document (handbook section 13)."""

    vendor: str | None = Field(description="Vendor name as written in the document, or null if not stated.")
    sku: str | None = Field(description="Campus Customs SKU, e.g. CC-HD-006, or null if not stated.")
    unit_price: float | None = Field(description="Quoted price per unit in US dollars, or null if not stated.")
    lead_time_days: int | None = Field(description="Lead time in days, as the number the document states, or null if not stated.")
    min_order: int | None = Field(description="Minimum order in units, or null if not stated.")
    decision: Literal["recommend", "do_not_recommend"] = Field(
        description="recommend only if all four handbook purchasing checks pass."
    )
    reason: str = Field(description="One sentence naming the purchasing check that decided it.")


@dataclass
class AgentDeps:
    """Run-time state passed to every tool (never sent to the model)."""

    data_dir: Path
    output_dir: Path
    doc_path: Path | None = None                            # the one document this run may read (design layer)
    defenses: frozenset[str] = frozenset()                  # any of "code", "design", "prompt"
    tool_calls: list[dict] = field(default_factory=list)    # audit trail for this run
    safety_notes: list[str] = field(default_factory=list)   # what each defense layer removed, blocked, or flagged
    document_text: str = ""                                 # exactly what read_document gave the model
