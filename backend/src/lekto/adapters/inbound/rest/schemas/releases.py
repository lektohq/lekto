"""The version of Lekto and the newest release (`GET /version`)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from lekto.core.domain.releases import Release


class ReleaseOut(BaseModel):
    version: str = Field(examples=["0.16.0"])
    published_at: datetime
    url: str = Field(description="The release's page on GitHub, with its notes.")

    @classmethod
    def of(cls, release: Release) -> "ReleaseOut":
        return cls(version=release.version, published_at=release.published_at, url=release.url)


class VersionOut(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "lekto_version": "0.15.6",
                    "api_version": "0.2",
                    "update_check": True,
                    "checked_at": "2026-11-19T21:00:00Z",
                    "latest": {
                        "version": "0.16.0",
                        "published_at": "2026-11-19T20:12:00Z",
                        "url": "https://github.com/lektohq/lekto/releases/tag/v0.16.0",
                    },
                    "update_available": True,
                }
            ]
        }
    )

    lekto_version: str = Field(description="The version of Lekto that answers (its release).")
    api_version: str = Field(description="The version of this API (`info.version`).")
    update_check: bool = Field(
        description="Whether this instance looks for releases (`LEKTO_UPDATE_CHECK`, and not a "
        "development state)."
    )
    checked_at: datetime | None = Field(description="The last look; null before the first.")
    latest: ReleaseOut | None = Field(
        description="The newest release that was news at the last look: newer, and stable if "
        "the running version is; null if there was none."
    )
    update_available: bool = Field(description="Whether `latest` is newer than the running one.")
