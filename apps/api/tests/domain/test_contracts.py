from decimal import Decimal
from typing import get_args

import pytest
from pydantic import BaseModel, ValidationError

from app.domain.enums import ALL_ROLE_FAMILIES, AppStatus, RoleFamily
from app.domain.jobs import (
    Compensation,
    JobPosting,
    SourceError,
    SourceNotFound,
    SourceTransientError,
)
from app.domain.preferences import Preferences
from app.integrations.llm.base import LLMResult, LLMTask, LLMUsage


def posting(**overrides: object) -> JobPosting:
    data: dict[str, object] = {
        "source": "greenhouse",
        "source_token": "acme",
        "external_id": "123",
        "title": "Software Engineer, New Grad",
        "description_text": "Build things.",
        "apply_url": "https://boards.greenhouse.io/acme/jobs/123",
        "canonical_url": "https://boards.greenhouse.io/acme/jobs/123",
    }
    data.update(overrides)
    return JobPosting.model_validate(data)


class TestJobPosting:
    def test_minimal_posting_gets_safe_defaults(self) -> None:
        p = posting()
        assert p.workplace_type == "unknown"
        assert p.employment_type == "unknown"
        assert p.locations == []
        assert p.compensation is None
        assert p.raw == {}

    def test_rejects_unknown_ats(self) -> None:
        with pytest.raises(ValidationError):
            posting(source="workday")

    def test_rejects_bad_url(self) -> None:
        with pytest.raises(ValidationError):
            posting(apply_url="not a url")

    def test_compensation_round_trips(self) -> None:
        p = posting(
            compensation={"min": 120000, "max": 160000, "currency": "USD", "interval": "year"}
        )
        assert p.compensation == Compensation(
            min=120000, max=160000, currency="USD", interval="year"
        )

    def test_source_errors_share_a_base(self) -> None:
        assert issubclass(SourceNotFound, SourceError)
        assert issubclass(SourceTransientError, SourceError)


class TestPreferences:
    def test_defaults_match_target_roles(self) -> None:
        p = Preferences()
        assert set(p.role_families) == {
            "sde",
            "mle",
            "aie",
            "research",
            "data_science",
            "robotics",
            "cv",
        }
        assert p.seniorities == ["intern", "new_grad", "junior", "unknown"]
        assert p.employment_types == ["full_time", "internship", "fellowship"]
        assert p.max_required_yoe == 3
        assert p.daily_quota == 10
        assert p.llm_daily_budget_usd == Decimal("1.00")

    def test_default_lists_are_not_shared(self) -> None:
        a, b = Preferences(), Preferences()
        a.role_families.append("other")
        assert "other" not in b.role_families

    def test_valid_timezone(self) -> None:
        assert Preferences(timezone="America/New_York").timezone == "America/New_York"

    @pytest.mark.parametrize("tz", ["Mars/Olympus", "", "../etc/passwd"])
    def test_invalid_timezone(self, tz: str) -> None:
        with pytest.raises(ValidationError, match="timezone"):
            Preferences(timezone=tz)

    @pytest.mark.parametrize("field", ["daily_quota", "max_required_yoe", "company_cooldown_days"])
    def test_rejects_negative(self, field: str) -> None:
        with pytest.raises(ValidationError):
            Preferences.model_validate({field: -1})


class TestLLMContracts:
    def test_task_values_match_config_suffixes(self) -> None:
        from app.config import Settings

        fields = Settings.model_fields
        for task in LLMTask:
            assert f"llm_model_{task.value}" in fields, task

    def test_generic_result_validates_payload(self) -> None:
        class Out(BaseModel):
            score: int

        usage = LLMUsage(model="m", input_tokens=10, output_tokens=5, cost_usd=Decimal("0.001"))
        result = LLMResult[Out](data=Out(score=80), usage=usage)
        assert result.data.score == 80
        assert result.usage.cached_input_tokens == 0


def test_role_family_tuple_matches_literal() -> None:
    assert ALL_ROLE_FAMILIES == get_args(RoleFamily)
    assert len(get_args(AppStatus)) == 10
