from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import EmploymentType, RoleFamily, Seniority, WorkplaceType

DEFAULT_ROLE_FAMILIES: tuple[RoleFamily, ...] = (
    "sde",
    "mle",
    "aie",
    "research",
    "data_science",
    "robotics",
    "cv",
)
DEFAULT_SENIORITIES: tuple[Seniority, ...] = ("intern", "new_grad", "junior", "unknown")
DEFAULT_EMPLOYMENT_TYPES: tuple[EmploymentType, ...] = ("full_time", "internship", "fellowship")
DEFAULT_WORKPLACE: tuple[WorkplaceType, ...] = ("remote", "hybrid", "onsite", "unknown")


class Preferences(BaseModel):
    """User job preferences. Defaults match the Product Owner's target roles (ARCHITECTURE.md).

    Filtering convention (S1-10): an *unknown* job attribute passes its rule. An empty list means
    "no constraint" for `countries` and `cities`.
    """

    role_families: list[RoleFamily] = Field(default_factory=lambda: list(DEFAULT_ROLE_FAMILIES))
    seniorities: list[Seniority] = Field(default_factory=lambda: list(DEFAULT_SENIORITIES))
    employment_types: list[EmploymentType] = Field(
        default_factory=lambda: list(DEFAULT_EMPLOYMENT_TYPES)
    )
    workplace: list[WorkplaceType] = Field(default_factory=lambda: list(DEFAULT_WORKPLACE))
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    needs_sponsorship: bool = False
    min_base_salary_usd: int | None = Field(default=None, ge=0)
    max_required_yoe: int = Field(default=3, ge=0)
    exclude_companies: list[UUID] = Field(default_factory=list)
    exclude_title_keywords: list[str] = Field(default_factory=list)
    require_any_keywords: list[str] = Field(default_factory=list)
    daily_quota: int = Field(default=10, ge=1, le=100)
    timezone: str = "UTC"
    company_cooldown_days: int = Field(default=30, ge=0)
    llm_daily_budget_usd: Decimal = Field(default=Decimal("1.00"), ge=0)

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"unknown IANA timezone: {v!r}") from e
        return v
