"""Strict request bodies (contract `additionalProperties: false` and x-validation)."""

from typing import Annotated, Literal, Union
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_website(value: str | None) -> str | None:
    """The contract declares `format: uri`; an annotated value must still have a scheme."""
    if value is None:
        return value
    parsed = urlparse(value)
    if not parsed.scheme or (parsed.scheme in ("http", "https") and not parsed.netloc):
        raise ValueError(f"website must be an absolute URI: {value!r}")
    return value


class _ProjectFields(_Strict):
    name: str = Field(min_length=2, max_length=160)
    company_name: str = Field(min_length=2, max_length=200)
    offer: str = Field(max_length=20000)
    website: str | None = Field(default=None, max_length=2000)
    markets: list[str] = Field(min_length=1, max_length=20)
    language_preferences: list[str] = Field(min_length=1, max_length=10)

    @field_validator("markets")
    @classmethod
    def _iso_markets(cls, value: list[str]) -> list[str]:
        for code in value:
            if len(code) != 2 or not code.isalpha() or code != code.upper():
                raise ValueError(f"market code must be ISO-3166 alpha-2: {code!r}")
        return value

    @field_validator("website")
    @classmethod
    def _uri_website(cls, value: str | None) -> str | None:
        return _check_website(value)

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> "_ProjectFields":
        """The contract types every project field non-nullable; `null` is not an omitted field."""
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        return self


class ProjectCreate(_ProjectFields):
    pass


class ProjectUpdate(_Strict):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    offer: str | None = Field(default=None, max_length=20000)
    website: str | None = Field(default=None, max_length=2000)
    markets: list[str] | None = Field(default=None, min_length=1, max_length=20)
    language_preferences: list[str] | None = Field(default=None, min_length=1, max_length=10)

    @field_validator("markets")
    @classmethod
    def _iso_markets(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        for code in value:
            if len(code) != 2 or not code.isalpha() or code != code.upper():
                raise ValueError(f"market code must be ISO-3166 alpha-2: {code!r}")
        return value

    @field_validator("website")
    @classmethod
    def _uri_website(cls, value: str | None) -> str | None:
        return _check_website(value)

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> "ProjectUpdate":
        """A partial update may omit fields, but an explicit `null` is not a value the DB accepts."""
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        return self


class ArchiveRequest(_Strict):
    """Contract `ArchiveRequest`: a required, auditable reason."""

    reason: str = Field(min_length=3, max_length=2000)


class BuyerFilters(_Strict):
    """Contract `BuyerFilters`. All optional; the route rejects a deferred non-empty filter."""

    q: str | None = Field(default=None, max_length=200)
    markets: list[str] | None = None
    buyer_types: list[str] | None = None
    fit: list[str] | None = None
    review: list[str] | None = None
    contact: list[str] | None = None
    suppressed: bool | None = None
    source_types: list[str] | None = None
    evidence_retrieved_after: str | None = None
    run_id: str | None = None
    list_id: str | None = None
    owner_membership_id: str | None = None


class SnapshotCreate(_Strict):
    filters: BuyerFilters = Field(default_factory=BuyerFilters)
    sort: Literal["best_fit", "name_asc"]
    requested_limit: int = Field(ge=1, le=1000)


class VersionedId(_Strict):
    id: str
    version: int = Field(ge=1)


class ExplicitSelection(_Strict):
    kind: Literal["explicit"]
    buyers: list[VersionedId] = Field(min_length=1, max_length=1000)


class SnapshotSelection(_Strict):
    kind: Literal["snapshot"]
    snapshot_id: str
    excluded_ids: list[str] = Field(default_factory=list, max_length=1000)


Selection = Annotated[Union[ExplicitSelection, SnapshotSelection], Field(discriminator="kind")]


class ReviewRequest(_Strict):
    selection: Selection
    status: Literal["accepted", "rejected", "needs_information"]
    reason: str = Field(min_length=3, max_length=2000)


class BuyerUpdate(_Strict):
    note: str | None = Field(default=None, max_length=4000)
    owner_membership_id: str | None = None

    @model_validator(mode="after")
    def _required_patch(self) -> "BuyerUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        if "note" in self.model_fields_set and self.note is None:
            raise ValueError("note must not be null")
        return self
