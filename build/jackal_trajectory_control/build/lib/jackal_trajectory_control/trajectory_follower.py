"""Closed-loop ROS 2 waypoint follower for Clearpath Jackal trajectories."""

from __future__ import annotations

import math
import time
from typing import List, Optional, Tuple

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

from .path_generators import MissionWaypoint, build_mission, build_path, transform_from_home


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a numeric value to a closed interval."""
    return max(minimum, min(maximum, value))


def normalize_angle(angle: float) -> float:
    """Normalize an angle to [-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


def quaternion_to_yaw(x: float, y: float, z: float, w: float) -> float:
    """Extract planar yaw from a quaternion."""
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


class JackalTrajectoryFollower(Node):
    """Follow a planned sequence of odometry-frame waypoints."""

    def __init__(self) -> None:
        super().__init__("trajectory_follower")
        self._declare_parameters()
        self._read_and_validate_parameters()

        self.current_x: Optional[float] = None
        self.current_y: Optional[float] = None
        self.current_yaw: Optional[float] = None
        self.last_odom_time: Optional[float] = None

        self.mission: List[MissionWaypoint] = self._create_mission()
        self.target_index = 0
        self.dwell_until: Optional[float] = None
        self.finished = False
        self.last_discovery_log = 0.0
        self.last_phase: Optional[Tuple[str, int]] = None

        self.cmd_publisher = self.create_publisher(
            Twist,
            self.cmd_vel_topic,
            10,
        )

        self.odom_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.odom_subscription = None

        if self.odom_topic:
            self._create_odom_subscription(self.odom_topic)
        else:
            self.discovery_timer = self.create_timer(
                0.5,
                self._discover_odom_topic,
            )

        self.control_timer = self.create_timer(
            1.0 / self.control_rate,
            self._control_loop,
        )

        self.get_logger().info(
            f"Trajectory: {self.trajectory} | grid: {self.columns}x{self.rows} | "
            f"spacing: ({self.spacing_x:.2f}, {self.spacing_y:.2f}) m"
        )
        self.get_logger().info(
            f"Home in odom: x={self.home_x:.3f}, y={self.home_y:.3f}, "
            f"yaw={self.home_yaw_deg:.1f} deg"
        )
        self.get_logger().info(
            f"Laps: {self.laps} | return mode: {self.return_mode} | "
            f"mission targets: {len(self.mission)}"
        )
        self.get_logger().info(f"Velocity topic: {self.cmd_vel_topic}")
        self.get_logger().info("Waiting for odometry before starting.")

    def _declare_parameters(self) -> None:
        self.declare_parameter("trajectory", "horizontal")
        self.declare_parameter("return_mode", "none")
        self.declare_parameter("laps", 1)

        self.declare_parameter("home_x", 0.0)
        self.declare_parameter("home_y", 0.0)
        self.declare_parameter("home_yaw_deg", 0.0)
        self.declare_parameter("go_home_first", True)

        self.declare_parameter("columns", 8)
        self.declare_parameter("rows", 5)
        self.declare_parameter("spacing_x", 1.0)
        self.declare_parameter("spacing_y", 1.0)
        self.declare_parameter("dwell_seconds", 0.5)

        self.declare_parameter("cmd_vel_topic", "cmd_vel")
        self.declare_parameter("odom_topic", "")

        self.declare_parameter("max_linear_speed", 0.30)
        self.declare_parameter("min_linear_speed", 0.06)
        self.declare_parameter("max_angular_speed", 0.70)
        self.declare_parameter("linear_gain", 0.80)
        self.declare_parameter("angular_gain", 1.80)
        self.declare_parameter("position_tolerance", 0.08)
        self.declare_parameter("yaw_tolerance_deg", 3.0)
        self.declare_parameter("turn_in_place_angle_deg", 31.5)
        self.declare_parameter("control_rate", 20.0)
        self.declare_parameter("odom_timeout", 1.0)

    def _read_and_validate_parameters(self) -> None:
        self.trajectory = str(self.get_parameter("trajectory").value).lower()
        self.return_mode = str(self.get_parameter("return_mode").value).lower()
        self.laps = int(self.get_parameter("laps").value)

        self.home_x = float(self.get_parameter("home_x").value)
        self.home_y = float(self.get_parameter("home_y").value)
        self.home_yaw_deg = float(self.get_parameter("home_yaw_deg").value)
        self.home_yaw = math.radians(self.home_yaw_deg)
        self.go_home_first = bool(self.get_parameter("go_home_first").value)

        self.columns = int(self.get_parameter("columns").value)
        self.rows = int(self.get_parameter("rows").value)
        self.spacing_x = float(self.get_parameter("spacing_x").value)
        self.spacing_y = float(self.get_parameter("spacing_y").value)
        self.dwell_seconds = float(self.get_parameter("dwell_seconds").value)

        self.cmd_vel_topic = str(self.get_parameter("cmd_vel_topic").value)
        self.odom_topic = str(self.get_parameter("odom_topic").value)

        self.max_linear_speed = float(self.get_parameter("max_linear_speed").value)
        self.min_linear_speed = float(self.get_parameter("min_linear_speed").value)
        self.max_angular_speed = float(self.get_parameter("max_angular_speed").value)
        self.linear_gain = float(self.get_parameter("linear_gain").value)
        self.angular_gain = float(self.get_parameter("angular_gain").value)
        self.position_tolerance = float(self.get_parameter("position_tolerance").value)
        self.yaw_tolerance = math.radians(
            float(self.get_parameter("yaw_tolerance_deg").value)
        )
        self.turn_in_place_angle = math.radians(
            float(self.get_parameter("turn_in_place_angle_deg").value)
        )
        self.control_rate = float(self.get_parameter("control_rate").value)
        self.odom_timeout = float(self.get_parameter("odom_timeout").value)

        if self.trajectory not in {"horizontal", "vertical", "spiral"}:
            raise ValueError(
                "trajectory must be horizontal, vertical, or spiral."
            )
        if self.return_mode not in {"none", "reverse"}:
            raise ValueError("return_mode must be none or reverse.")
        if self.laps < 1:
            raise ValueError("laps must be at least 1.")
        if self.laps > 1 and self.return_mode != "reverse":
            raise ValueError(
                "laps > 1 requires return_mode=reverse so every lap starts at home."
            )
        if self.columns < 1 or self.rows < 1:
            raise ValueError("columns and rows must be at least 1.")
        if self.spacing_x <= 0.0 or self.spacing_y <= 0.0:
            raise ValueError("spacing_x and spacing_y must be positive.")
        if self.dwell_seconds < 0.0:
            raise ValueError("dwell_seconds cannot be negative.")
        if self.min_linear_speed < 0.0:
            raise ValueError("min_linear_speed cannot be negative.")
        if self.min_linear_speed > self.max_linear_speed:
            raise ValueError(
                "min_linear_speed cannot exceed max_linear_speed."
            )
        positive_values = {
            "max_linear_speed": self.max_linear_speed,
            "max_angular_speed": self.max_angular_speed,
            "linear_gain": self.linear_gain,
            "angular_gain": self.angular_gain,
            "position_tolerance": self.position_tolerance,
            "yaw_tolerance_deg": math.degrees(self.yaw_tolerance),
            "turn_in_place_angle_deg": math.degrees(self.turn_in_place_angle),
            "control_rate": self.control_rate,
            "odom_timeout": self.odom_timeout,
        }
        for name, value in positive_values.items():
            if value <= 0.0:
                raise ValueError(f"{name} must be positive.")

    def _create_mission(self) -> List[MissionWaypoint]:
        local_path = build_path(
            trajectory=self.trajectory,
            columns=self.columns,
            rows=self.rows,
            spacing_x=self.spacing_x,
            spacing_y=self.spacing_y,
        )
        odom_path = transform_from_home(
            local_path,
            home_x=self.home_x,
            home_y=self.home_y,
            home_yaw=self.home_yaw,
        )
        return build_mission(
            odom_path,
            home_x=self.home_x,
            home_y=self.home_y,
            home_yaw=self.home_yaw,
            laps=self.laps,
            return_mode=self.return_mode,
            go_home_first=self.go_home_first,
            dwell_seconds=self.dwell_seconds,
        )

    def _discover_odom_topic(self) -> None:
        topics = self.get_topic_names_and_types()
        candidates = [
            name
            for name, types in topics
            if "nav_msgs/msg/Odometry" in types
        ]

        if not candidates:
            now = time.monotonic()
            if now - self.last_discovery_log >= 3.0:
                self.get_logger().warning(
                    "No nav_msgs/msg/Odometry topic found. "
                    "Check with: ros2 topic list -t | grep Odometry"
                )
                self.last_discovery_log = now
            return

        def priority(topic: str) -> Tuple[int, int]:
            preferred = (
                "platform_velocity_controller/odom",
                "odometry/filtered",
                "platform/odom",
                "/odom",
            )
            for index, fragment in enumerate(preferred):
                if fragment in topic:
                    return index, len(topic)
            return len(preferred), len(topic)

        selected_topic = sorted(candidates, key=priority)[0]
        self._create_odom_subscription(selected_topic)
        if hasattr(self, "discovery_timer"):
            self.discovery_timer.cancel()

    def _create_odom_subscription(self, topic: str) -> None:
        self.odom_topic = topic
        self.odom_subscription = self.create_subscription(
            Odometry,
            topic,
            self._odom_callback,
            self.odom_qos,
        )
        self.get_logger().info(f"Odometry topic: {topic}")

    def _odom_callback(self, message: Odometry) -> None:
        pose = message.pose.pose
        self.current_x = pose.position.x
        self.current_y = pose.position.y
        self.current_yaw = quaternion_to_yaw(
            pose.orientation.x,
            pose.orientation.y,
            pose.orientation.z,
            pose.orientation.w,
        )
        self.last_odom_time = time.monotonic()

    def _control_loop(self) -> None:
        if self.finished:
            self._publish_stop()
            return

        if self.target_index >= len(self.mission):
            self._finish()
            return

        if (
            self.current_x is None
            or self.current_y is None
            or self.current_yaw is None
        ):
            return

        if (
            self.last_odom_time is None
            or time.monotonic() - self.last_odom_time > self.odom_timeout
        ):
            self._publish_stop()
            self.get_logger().error(
                "Odometry timeout. Robot stopped.",
                throttle_duration_sec=2.0,
            )
            return

        now = time.monotonic()
        if self.dwell_until is not None:
            self._publish_stop()
            if now >= self.dwell_until:
                self.dwell_until = None
                self.target_index += 1
            return

        target = self.mission[self.target_index]
        phase_key = (target.phase, target.lap)
        if phase_key != self.last_phase:
            self.last_phase = phase_key
            if target.phase == "go_home":
                self.get_logger().info("Phase: move to home and align home yaw.")
            else:
                self.get_logger().info(
                    f"Phase: {target.phase} | lap {target.lap}/{self.laps}."
                )

        delta_x = target.x - self.current_x
        delta_y = target.y - self.current_y
        distance = math.hypot(delta_x, delta_y)

        if distance > self.position_tolerance:
            target_heading = math.atan2(delta_y, delta_x)
            heading_error = normalize_angle(target_heading - self.current_yaw)
            self._drive_to_position(distance, heading_error)
            return

        if target.required_yaw is not None:
            yaw_error = normalize_angle(target.required_yaw - self.current_yaw)
            if abs(yaw_error) > self.yaw_tolerance:
                self._rotate_in_place(yaw_error)
                return

        self._reach_target(target)

    def _drive_to_position(self, distance: float, heading_error: float) -> None:
        command = Twist()

        if abs(heading_error) > self.turn_in_place_angle:
            command.angular.z = clamp(
                self.angular_gain * heading_error,
                -self.max_angular_speed,
                self.max_angular_speed,
            )
        else:
            speed_scale = max(
                0.15,
                1.0 - abs(heading_error) / self.turn_in_place_angle,
            )
            command.linear.x = clamp(
                self.linear_gain * distance,
                self.min_linear_speed,
                self.max_linear_speed,
            ) * speed_scale
            command.angular.z = clamp(
                self.angular_gain * heading_error,
                -self.max_angular_speed,
                self.max_angular_speed,
            )

        self.cmd_publisher.publish(command)

    def _rotate_in_place(self, yaw_error: float) -> None:
        command = Twist()
        command.angular.z = clamp(
            self.angular_gain * yaw_error,
            -self.max_angular_speed,
            self.max_angular_speed,
        )
        self.cmd_publisher.publish(command)

    def _reach_target(self, target: MissionWaypoint) -> None:
        self._publish_stop()
        self.get_logger().info(
            f"Target {self.target_index + 1}/{len(self.mission)} reached | "
            f"phase={target.phase} | lap={target.lap} | "
            f"x={target.x:.2f}, y={target.y:.2f}"
        )

        if target.dwell_seconds > 0.0:
            self.dwell_until = time.monotonic() + target.dwell_seconds
        else:
            self.target_index += 1

    def _finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        self._publish_stop(repetitions=10)
        self.get_logger().info(
            "Mission completed. The Jackal is stopped."
        )

    def _publish_stop(self, repetitions: int = 1) -> None:
        stop = Twist()
        for _ in range(repetitions):
            self.cmd_publisher.publish(stop)

    def stop(self) -> None:
        self._publish_stop(repetitions=10)


def main(args=None) -> None:
    rclpy.init(args=args)
    node: Optional[JackalTrajectoryFollower] = None

    try:
        node = JackalTrajectoryFollower()
        rclpy.spin(node)
    except KeyboardInterrupt:
        if node is not None:
            node.get_logger().info("Interrupted by user. Stopping Jackal.")
    except Exception as exc:  # noqa: BLE001 - report configuration/runtime errors to ROS.
        if node is not None:
            node.get_logger().fatal(str(exc))
        else:
            print(f"Fatal error: {exc}")
    finally:
        if node is not None:
            node.stop()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
