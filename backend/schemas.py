"""Data contracts for A11y Pilot.

Single source of truth for the API, LLM output validation, and the frontend.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

Impact = Literal["critical", "serious", "moderate", "minor"]
IssueSource = Literal["axe", "llm"]
FixStatus = Literal[
    "proposed",
    "needs_human",
    "rejected",
    "applied",
    "retried_applied",
    "reverted",
    "failed",
]
RunStatus = Literal[
    "created",
    "scanning",
    "scanned",
    "auditing",
    "fixing",
    "awaiting_review",
    "applying",
    "completed",
    "failed",
]


class Issue(BaseModel):
    id: str  # "iss_001" ...
    source: IssueSource
    rule_id: str  # axe rule id or "llm-alt-quality", "llm-link-purpose", ...
    impact: Impact
    wcag: list[str] = Field(default_factory=list)  # e.g. ["1.1.1"]
    selector: str  # single CSS selector string
    html: str  # outerHTML snippet, truncated to 500 chars
    message: str
    help_url: str | None = None
    fixable: bool = True  # False when selector is complex (iframe/shadow DOM) etc.


# ---- Patches (discriminated union; this is the ONLY thing the LLM may output as an action) ----
class SetAttr(BaseModel):
    op: Literal["set_attr"] = "set_attr"
    selector: str
    name: str
    value: str


class RemoveAttr(BaseModel):
    op: Literal["remove_attr"] = "remove_attr"
    selector: str
    name: str


class SetText(BaseModel):
    op: Literal["set_text"] = "set_text"
    selector: str
    value: str


class WrapLabel(BaseModel):
    op: Literal["wrap_label"] = "wrap_label"
    selector: str
    label_text: str


class AddCss(BaseModel):
    op: Literal["add_css"] = "add_css"
    selector: str
    property: str
    value: str


class ChangeTag(BaseModel):
    op: Literal["change_tag"] = "change_tag"
    selector: str
    new_tag: str


Patch = Annotated[
    SetAttr | RemoveAttr | SetText | WrapLabel | AddCss | ChangeTag,
    Field(discriminator="op"),
]

patch_adapter = TypeAdapter(Patch)


def parse_patch(data: object) -> Patch:
    """Validate and parse a dictionary or model into a valid Patch instance."""
    return patch_adapter.validate_python(data)


class FixSuggestion(BaseModel):
    id: str  # "fix_001"
    issue_id: str
    explanation: str  # max 2 sentences, plain language, says who is affected
    wcag: str  # primary criterion, e.g. "1.1.1"
    patch: Patch | None = None  # None when needs_human
    confidence: float = Field(ge=0.0, le=1.0)
    needs_human: bool = False
    human_note: str | None = None  # what a human should check
    before_snippet: str | None = None  # filled by backend after dry-run
    after_snippet: str | None = None
    diff: str | None = None  # unified diff of snippets (backend-generated)
    status: FixStatus = "proposed"
    attempts: int = 0
    verification_note: str | None = None


class ScoreBreakdown(BaseModel):
    score: int  # 0..100
    penalty: int
    by_impact: dict[str, int]  # counts of affected nodes per impact (uncapped)
    rules_violated: int


class AgentEvent(BaseModel):
    seq: int
    ts: float
    type: Literal[
        "step_started",
        "step_completed",
        "issue_found",
        "fix_proposed",
        "fix_applied",
        "fix_retry",
        "fix_reverted",
        "verification_done",
        "run_completed",
        "error",
    ]
    step: str | None = None  # "scan" | "audit" | "fix" | "verify" | "report"
    message: str
    data: dict | None = None


class ScanReport(BaseModel):
    run_id: str
    source_url: str | None = None
    page_title: str | None = None
    status: RunStatus
    score_before: ScoreBreakdown | None = None
    score_after: ScoreBreakdown | None = None
    issues: list[Issue] = Field(default_factory=list)
    fixes: list[FixSuggestion] = Field(default_factory=list)
    aria_before: str | None = None
    aria_after: str | None = None
    html_original_bytes: int | None = None
    limitations: list[str] = Field(default_factory=list)
    needs_manual_checks: list[str] = Field(default_factory=list)
    llm_provider: str | None = None
    duration_seconds: float | None = None


# ---- API Request Models ----
class ScanRequest(BaseModel):
    url: str | None = None
    html: str | None = None
    base_url: str | None = None
    language: Literal["en", "hinglish"] | None = "en"


class ApplyRequest(BaseModel):
    approved_fix_ids: list[str]
