"""Pure trajectory-generation utilities for the Jackal trajectory controller."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class MissionWaypoint:
    """One target in the complete mission plan."""

    x: float
    y: float
    phase: str
    lap: int
    dwell_seconds: float
    required_yaw: Optional[float] = None


def build_horizontal_serpentine(
    columns: int,
    rows: int,
    spacing_x: float,
    spacing_y: float,
) -> List[Point]:
    """Build a row-wise serpentine: even rows go right, odd rows go left."""
    points: List[Point] = []

    for row in range(rows):
        columns_in_row = (
            range(columns)
            if row % 2 == 0
            else range(columns - 1, -1, -1)
        )
        for column in columns_in_row:
            points.append((column * spacing_x, row * spacing_y))

    return points


def build_vertical_serpentine(
    columns: int,
    rows: int,
    spacing_x: float,
    spacing_y: float,
) -> List[Point]:
    """Build a column-wise serpentine: even columns go up, odd columns go down."""
    points: List[Point] = []

    for column in range(columns):
        rows_in_column = (
            range(rows)
            if column % 2 == 0
            else range(rows - 1, -1, -1)
        )
        for row in rows_in_column:
            points.append((column * spacing_x, row * spacing_y))

    return points


def build_inverse_horizontal_serpentine(
    columns: int,
    rows: int,
    spacing_x: float,
    spacing_y: float,
) -> List[Point]:
    """Build the horizontal serpentine in exact reverse waypoint order.

    The first point is the far endpoint of the normal horizontal serpentine and
    the last point is home. The controller first transits to the far endpoint,
    then follows this list back to home.
    """
    return list(
        reversed(
            build_horizontal_serpentine(
                columns,
                rows,
                spacing_x,
                spacing_y,
            )
        )
    )


def build_inward_spiral(
    columns: int,
    rows: int,
    spacing_x: float,
    spacing_y: float,
) -> List[Point]:
    """Build a clockwise rectangular spiral from the perimeter to the centre."""
    points: List[Point] = []
    left = 0
    right = columns - 1
    bottom = 0
    top = rows - 1

    while left <= right and bottom <= top:
        for column in range(left, right + 1):
            points.append((column * spacing_x, bottom * spacing_y))
        bottom += 1

        for row in range(bottom, top + 1):
            points.append((right * spacing_x, row * spacing_y))
        right -= 1

        if bottom <= top:
            for column in range(right, left - 1, -1):
                points.append((column * spacing_x, top * spacing_y))
            top -= 1

        if left <= right:
            for row in range(top, bottom - 1, -1):
                points.append((left * spacing_x, row * spacing_y))
            left += 1

    return points


def build_path(
    trajectory: str,
    columns: int,
    rows: int,
    spacing_x: float,
    spacing_y: float,
) -> List[Point]:
    """Create one path in the home coordinate frame."""
    builders = {
        "horizontal": build_horizontal_serpentine,
        "vertical": build_vertical_serpentine,
        "inverse": build_inverse_horizontal_serpentine,
        "spiral": build_inward_spiral,
    }

    try:
        builder = builders[trajectory]
    except KeyError as exc:
        supported = ", ".join(sorted(builders))
        raise ValueError(
            f"Unsupported trajectory '{trajectory}'. Supported: {supported}."
        ) from exc

    return builder(columns, rows, spacing_x, spacing_y)


def transform_from_home(
    points: Sequence[Point],
    home_x: float,
    home_y: float,
    home_yaw: float,
) -> List[Point]:
    """Rotate and translate local path points into the odometry frame."""
    cos_yaw = math.cos(home_yaw)
    sin_yaw = math.sin(home_yaw)
    transformed: List[Point] = []

    for local_x, local_y in points:
        odom_x = home_x + local_x * cos_yaw - local_y * sin_yaw
        odom_y = home_y + local_x * sin_yaw + local_y * cos_yaw
        transformed.append((odom_x, odom_y))

    return transformed


def build_mission(
    outbound_points: Sequence[Point],
    *,
    home_x: float,
    home_y: float,
    home_yaw: float,
    laps: int,
    return_mode: str,
    go_home_first: bool,
    dwell_seconds: float,
) -> List[MissionWaypoint]:
    """Build a normal mission, including optional exact reverse returns."""
    if not outbound_points:
        raise ValueError("The outbound path cannot be empty.")
    if laps < 1:
        raise ValueError("laps must be at least 1.")
    if return_mode not in {"none", "reverse"}:
        raise ValueError("return_mode must be 'none' or 'reverse'.")
    if laps > 1 and return_mode != "reverse":
        raise ValueError(
            "Multiple laps require return_mode='reverse' so each new lap starts at home."
        )

    mission: List[MissionWaypoint] = []

    if go_home_first:
        mission.append(
            MissionWaypoint(
                x=home_x,
                y=home_y,
                phase="go_home",
                lap=0,
                dwell_seconds=0.0,
                required_yaw=home_yaw,
            )
        )

    for lap_index in range(1, laps + 1):
        outbound_for_lap = (
            outbound_points
            if lap_index == 1 or return_mode != "reverse"
            else outbound_points[1:]
        )

        for x, y in outbound_for_lap:
            mission.append(
                MissionWaypoint(
                    x=x,
                    y=y,
                    phase="outbound",
                    lap=lap_index,
                    dwell_seconds=dwell_seconds,
                )
            )

        if return_mode == "reverse":
            reverse_points = list(reversed(outbound_points[:-1]))
            for reverse_index, (x, y) in enumerate(reverse_points):
                is_home = reverse_index == len(reverse_points) - 1
                mission.append(
                    MissionWaypoint(
                        x=x,
                        y=y,
                        phase="return",
                        lap=lap_index,
                        dwell_seconds=dwell_seconds,
                        required_yaw=home_yaw if is_home else None,
                    )
                )

    return mission


def build_inverse_mission(
    inverse_points: Sequence[Point],
    *,
    home_x: float,
    home_y: float,
    home_yaw: float,
    laps: int,
    go_home_first: bool,
    dwell_seconds: float,
) -> List[MissionWaypoint]:
    """Build an inverse horizontal mission that finishes at home.

    Each lap first moves directly from home to the far endpoint of the normal
    horizontal serpentine. It then follows the horizontal serpentine in exact
    reverse waypoint order until reaching home.
    """
    if not inverse_points:
        raise ValueError("The inverse path cannot be empty.")
    if laps < 1:
        raise ValueError("laps must be at least 1.")

    mission: List[MissionWaypoint] = []

    if go_home_first:
        mission.append(
            MissionWaypoint(
                x=home_x,
                y=home_y,
                phase="go_home",
                lap=0,
                dwell_seconds=0.0,
                required_yaw=home_yaw,
            )
        )

    for lap_index in range(1, laps + 1):
        far_x, far_y = inverse_points[0]
        mission.append(
            MissionWaypoint(
                x=far_x,
                y=far_y,
                phase="inverse_transit",
                lap=lap_index,
                dwell_seconds=dwell_seconds,
            )
        )

        for point_index, (x, y) in enumerate(inverse_points[1:], start=1):
            is_home = point_index == len(inverse_points) - 1
            mission.append(
                MissionWaypoint(
                    x=x,
                    y=y,
                    phase="inverse_scan",
                    lap=lap_index,
                    dwell_seconds=dwell_seconds,
                    required_yaw=home_yaw if is_home else None,
                )
            )

    return mission
