"""JSON models for the map payload, snapshots and state-stream frames."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from vrobot_sim.map_model import TopologyMap
from vrobot_sim.snapshots import TickSnapshot

RunMode = Literal["unconfigured", "configured", "running", "paused"]


class MapNodePayload(BaseModel):
    node_id: str
    x_m: float
    y_m: float


class MapEdgePayload(BaseModel):
    edge_id: str
    from_node_id: str
    to_node_id: str
    direction: str
    lane_width_m: float


class MapZonePayload(BaseModel):
    zone_id: str
    name: str
    capacity: int
    edge_ids: list[str]


class MapPayload(BaseModel):
    map_id: str
    nodes: list[MapNodePayload]
    edges: list[MapEdgePayload]
    zones: list[MapZonePayload]

    @classmethod
    def from_topology(cls, topology: TopologyMap) -> "MapPayload":
        return cls(
            map_id=topology.map_id,
            nodes=[
                MapNodePayload(node_id=node.node_id, x_m=node.x, y_m=node.y)
                for node in topology.nodes
            ],
            edges=[
                MapEdgePayload(
                    edge_id=edge.edge_id,
                    from_node_id=edge.from_node_id,
                    to_node_id=edge.to_node_id,
                    direction=edge.direction.value,
                    lane_width_m=edge.lane_width_m,
                )
                for edge in topology.edges
            ],
            zones=[
                MapZonePayload(
                    zone_id=zone.zone_id,
                    name=zone.name,
                    capacity=zone.capacity,
                    edge_ids=list(zone.edge_ids),
                )
                for zone in topology.zones
            ],
        )


class RobotPayload(BaseModel):
    robot_id: str
    x_m: float
    y_m: float
    theta_rad: float
    v_mps: float
    omega_radps: float
    status: str
    estop_reason: str


class ZonePayload(BaseModel):
    zone_id: str
    capacity: int
    holder_robot_ids: list[str]
    waiting_robot_ids: list[str]


class SnapshotPayload(BaseModel):
    tick_index: int
    sim_time_s: float
    robots: list[RobotPayload]
    zones: list[ZonePayload]

    @classmethod
    def from_tick(cls, snapshot: TickSnapshot) -> "SnapshotPayload":
        return cls(
            tick_index=snapshot.tick_index,
            sim_time_s=snapshot.sim_time_s,
            robots=[
                RobotPayload(
                    robot_id=robot.robot_id,
                    x_m=robot.x_m,
                    y_m=robot.y_m,
                    theta_rad=robot.theta_rad,
                    v_mps=robot.v_mps,
                    omega_radps=robot.omega_radps,
                    status=robot.status.value,
                    estop_reason=robot.estop_reason.value,
                )
                for robot in snapshot.robots
            ],
            zones=[
                ZonePayload(
                    zone_id=zone.zone_id,
                    capacity=zone.capacity,
                    holder_robot_ids=list(zone.holder_robot_ids),
                    waiting_robot_ids=list(zone.waiting_robot_ids),
                )
                for zone in snapshot.zones
            ],
        )


class StatusFrame(BaseModel):
    kind: Literal["status"] = "status"
    mode: RunMode
    snapshot: SnapshotPayload | None = None


class TickFrame(BaseModel):
    kind: Literal["tick"] = "tick"
    mode: Literal["running"] = "running"
    snapshot: SnapshotPayload
