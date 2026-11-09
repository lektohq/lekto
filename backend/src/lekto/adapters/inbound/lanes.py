"""The lanes a filter of documents names, as REST and MCP take them: each lane, and
`processing` for the documents that have none yet."""

from enum import StrEnum

from lekto.core.domain.pipeline import Lane
from lekto.core.domain.search import PROCESSING, lane_value


class LaneFilter(StrEnum):
    """A lane, or `processing`: documents that have no lane yet."""

    GREEN = Lane.GREEN.value
    YELLOW = Lane.YELLOW.value
    RED = Lane.RED.value
    PROCESSING = PROCESSING


LANES: dict[LaneFilter, Lane | None] = {
    LaneFilter(lane_value(lane)): lane for lane in (*Lane, None)
}
"""Every lane, and none, by its name in a filter (a lane without a member fails here, at
import)."""
