"""Built-in example topology maps.

Only ``minimal`` and ``demo`` exist as loadable identifiers; persistence and map file
formats are deferred to WI-map-editor.
"""

from __future__ import annotations

from typing import Final

from vrobot_sim.map_model import TopologyMap
from vrobot_sim.maps.demo import DEMO_MAP, DEMO_MAP_ID
from vrobot_sim.maps.minimal import MINIMAL_MAP, MINIMAL_MAP_ID

BUILT_IN_MAP_IDS: Final[frozenset[str]] = frozenset({MINIMAL_MAP_ID, DEMO_MAP_ID})

_MAPS: Final[dict[str, TopologyMap]] = {MINIMAL_MAP_ID: MINIMAL_MAP, DEMO_MAP_ID: DEMO_MAP}


def load_map(map_id: str) -> TopologyMap:
    return _MAPS[map_id]
