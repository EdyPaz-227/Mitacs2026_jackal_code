import math

import pytest

from jackal_trajectory_control.path_generators import (
    build_horizontal_serpentine,
    build_inverse_horizontal_serpentine,
    build_inverse_mission,
    build_inward_spiral,
    build_mission,
    build_vertical_serpentine,
    transform_from_home,
)


def test_horizontal_serpentine_8x5_has_40_unique_points():
    points = build_horizontal_serpentine(8, 5, 1.0, 1.0)
    assert len(points) == 40
    assert len(set(points)) == 40
    assert points[:8] == [(x, 0.0) for x in range(8)]
    assert points[8:16] == [(x, 1.0) for x in range(7, -1, -1)]


def test_vertical_serpentine_8x5_has_40_unique_points():
    points = build_vertical_serpentine(8, 5, 1.0, 1.0)
    assert len(points) == 40
    assert len(set(points)) == 40
    assert points[:5] == [(0.0, y) for y in range(5)]
    assert points[5:10] == [(1.0, y) for y in range(4, -1, -1)]


def test_inverse_horizontal_is_exact_reverse():
    normal = build_horizontal_serpentine(8, 5, 1.0, 1.0)
    inverse = build_inverse_horizontal_serpentine(8, 5, 1.0, 1.0)
    assert inverse == list(reversed(normal))
    assert inverse[-1] == (0.0, 0.0)


def test_inverse_mission_transits_to_far_point_then_finishes_home():
    inverse = [(2.0, 1.0), (1.0, 1.0), (0.0, 0.0)]
    mission = build_inverse_mission(
        inverse,
        home_x=0.0,
        home_y=0.0,
        home_yaw=0.0,
        laps=1,
        go_home_first=True,
        dwell_seconds=0.5,
    )
    coordinates = [(waypoint.x, waypoint.y) for waypoint in mission]
    assert coordinates == [(0.0, 0.0), (2.0, 1.0), (1.0, 1.0), (0.0, 0.0)]
    assert mission[-1].required_yaw == 0.0


def test_spiral_8x5_covers_every_grid_point_once():
    points = build_inward_spiral(8, 5, 1.0, 1.0)
    expected = {(x, y) for x in range(8) for y in range(5)}
    assert len(points) == 40
    assert set(points) == expected


def test_transform_from_home_rotates_path_90_degrees():
    result = transform_from_home([(0.0, 0.0), (1.0, 0.0)], 2.0, 3.0, math.pi / 2)
    assert result[0] == pytest.approx((2.0, 3.0))
    assert result[1] == pytest.approx((2.0, 4.0))


def test_reverse_mission_returns_through_exact_reverse_points():
    outbound = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
    mission = build_mission(
        outbound,
        home_x=0.0,
        home_y=0.0,
        home_yaw=0.0,
        laps=1,
        return_mode="reverse",
        go_home_first=False,
        dwell_seconds=0.5,
    )
    coordinates = [(waypoint.x, waypoint.y) for waypoint in mission]
    assert coordinates == [
        (0.0, 0.0),
        (1.0, 0.0),
        (2.0, 0.0),
        (1.0, 0.0),
        (0.0, 0.0),
    ]
    assert mission[-1].required_yaw == 0.0


def test_multiple_laps_require_reverse_return():
    with pytest.raises(ValueError):
        build_mission(
            [(0.0, 0.0), (1.0, 0.0)],
            home_x=0.0,
            home_y=0.0,
            home_yaw=0.0,
            laps=2,
            return_mode="none",
            go_home_first=True,
            dwell_seconds=0.5,
        )
