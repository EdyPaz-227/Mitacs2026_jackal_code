"""Joystick-triggered closed-loop trajectory controller for a Clearpath Jackal."""

from __future__ import annotations

import math
import time
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import Joy
from std_msgs.msg import String

from .path_generators import (
    MissionWaypoint,
    build_inverse_mission,
    build_mission,
    build_path,
    transform_from_home,
)


class ControllerState(str, Enum):
    """High-level controller state."""

    WAITING_FOR_HOME = "WAITING_FOR_HOME"
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    RETURNING_HOME = "RETURNING_HOME"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


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


class JoystickTrajectoryController(Node):
    """Wait for PlayStation button commands and follow odometry waypoints."""

    SUPPORTED_MODES = ("horizontal", "vertical", "inverse")

    def __init__(self) -> None:
        super().__init__("joystick_trajectory_controller")
        self._declare_parameters()
        self._read_and_validate_parameters()

        self.current_x: Optional[float] = None
        self.current_y: Optional[float] = None
        self.current_yaw: Optional[float] = None
        self.last_odom_time: Optional[float] = None

        self.home_x: Optional[float] = None
        self.home_y: Optional[float] = None
        self.home_yaw: Optional[float] = None

        self.state = ControllerState.WAITING_FOR_HOME
        self.mode_index = self.trajectory_modes.index(self.initial_mode)
        self.mission: List[MissionWaypoint] = []
        self.target_index = 0
        self.dwell_until: Optional[float] = None
        self.last_phase: Optional[Tuple[str, int]] = None

        self.previous_buttons: List[int] = []
        self.manual_buttons_down = False
        self.triangle_is_down = False
        self.triangle_pressed_at: Optional[float] = None
        self.triangle_hold_triggered = False

        self.cmd_publisher = self.create_publisher(Twist, self.cmd_vel_topic, 10)
        self.status_publisher = self.create_publisher(String, self.status_topic, 10)

        odom_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.odom_subscription = self.create_subscription(
            Odometry,
            self.odom_topic,
            self._odom_callback,
            odom_qos,
        )
        joy_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.joy_subscription = self.create_subscription(
            Joy,
            self.joy_topic,
            self._joy_callback,
            joy_qos,
        )

        self.control_timer = self.create_timer(
            1.0 / self.control_rate,
            self._control_loop,
        )
        self.add_on_set_parameters_callback(self._on_parameters_changed)

        self.get_logger().info("Joystick trajectory controller is ready.")
        self.get_logger().info(f"Velocity input: {self.cmd_vel_topic}")
        self.get_logger().info(f"Odometry: {self.odom_topic}")
        self.get_logger().info(f"Joystick: {self.joy_topic}")
        self.get_logger().info(
            "Buttons: X=start, Circle=change mode, Square=set home, "
            "Triangle=cancel/hold for home, L1/R1=manual override."
        )
        self.get_logger().info("Press Square at the desired home pose.")
        self._publish_status()

    def _declare_parameters(self) -> None:
        self.declare_parameter("trajectory_modes", ["horizontal", "vertical", "inverse"])
        self.declare_parameter("initial_mode", "horizontal")
        self.declare_parameter("return_mode", "reverse")
        self.declare_parameter("laps", 1)
        self.declare_parameter("go_home_first", True)

        self.declare_parameter("columns", 8)
        self.declare_parameter("rows", 5)
        self.declare_parameter("spacing_x", 1.0)
        self.declare_parameter("spacing_y", 1.0)
        self.declare_parameter("dwell_seconds", 0.5)

        self.declare_parameter("cmd_vel_topic", "cmd_vel")
        self.declare_parameter("odom_topic", "platform/odom/filtered")
        self.declare_parameter("joy_topic", "joy_teleop/joy")
        self.declare_parameter("status_topic", "trajectory/status")

        self.declare_parameter("button_x", 0)
        self.declare_parameter("button_circle", 1)
        self.declare_parameter("button_square", 2)
        self.declare_parameter("button_triangle", 3)
        self.declare_parameter("button_l1", 9)
        self.declare_parameter("button_r1", 10)
        self.declare_parameter("triangle_hold_seconds", 1.0)
        self.declare_parameter("return_requires_hold", True)

        self.declare_parameter("max_linear_speed", 0.20)
        self.declare_parameter("min_linear_speed", 0.05)
        self.declare_parameter("max_angular_speed", 0.40)
        self.declare_parameter("linear_gain", 0.80)
        self.declare_parameter("angular_gain", 1.80)
        self.declare_parameter("position_tolerance", 0.15)
        self.declare_parameter("yaw_tolerance_deg", 8.0)
        self.declare_parameter("turn_in_place_angle_deg", 31.5)
        self.declare_parameter("control_rate", 20.0)
        self.declare_parameter("odom_timeout", 1.0)

    def _read_and_validate_parameters(self) -> None:
        self.trajectory_modes = [
            str(value).lower()
            for value in self.get_parameter("trajectory_modes").value
        ]
        self.initial_mode = str(self.get_parameter("initial_mode").value).lower()
        self.return_mode = str(self.get_parameter("return_mode").value).lower()
        self.laps = int(self.get_parameter("laps").value)
        self.go_home_first = bool(self.get_parameter("go_home_first").value)

        self.columns = int(self.get_parameter("columns").value)
        self.rows = int(self.get_parameter("rows").value)
        self.spacing_x = float(self.get_parameter("spacing_x").value)
        self.spacing_y = float(self.get_parameter("spacing_y").value)
        self.dwell_seconds = float(self.get_parameter("dwell_seconds").value)

        self.cmd_vel_topic = str(self.get_parameter("cmd_vel_topic").value)
        self.odom_topic = str(self.get_parameter("odom_topic").value)
        self.joy_topic = str(self.get_parameter("joy_topic").value)
        self.status_topic = str(self.get_parameter("status_topic").value)

        self.button_x = int(self.get_parameter("button_x").value)
        self.button_circle = int(self.get_parameter("button_circle").value)
        self.button_square = int(self.get_parameter("button_square").value)
        self.button_triangle = int(self.get_parameter("button_triangle").value)
        self.button_l1 = int(self.get_parameter("button_l1").value)
        self.button_r1 = int(self.get_parameter("button_r1").value)
        self.triangle_hold_seconds = float(
            self.get_parameter("triangle_hold_seconds").value
        )
        self.return_requires_hold = bool(
            self.get_parameter("return_requires_hold").value
        )

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

        self._validate_configuration()

    def _validate_configuration(self) -> None:
        if not self.trajectory_modes:
            raise ValueError("trajectory_modes cannot be empty.")
        unsupported = set(self.trajectory_modes) - set(self.SUPPORTED_MODES)
        if unsupported:
            raise ValueError(f"Unsupported trajectory modes: {sorted(unsupported)}")
        if self.initial_mode not in self.trajectory_modes:
            raise ValueError("initial_mode must be present in trajectory_modes.")
        if self.return_mode not in {"none", "reverse"}:
            raise ValueError("return_mode must be none or reverse.")
        if self.laps < 1:
            raise ValueError("laps must be at least 1.")
        if self.laps > 1 and self.return_mode != "reverse":
            raise ValueError("laps > 1 requires return_mode=reverse.")
        if self.columns < 1 or self.rows < 1:
            raise ValueError("columns and rows must be at least 1.")
        if self.spacing_x <= 0.0 or self.spacing_y <= 0.0:
            raise ValueError("spacing_x and spacing_y must be positive.")
        if self.dwell_seconds < 0.0:
            raise ValueError("dwell_seconds cannot be negative.")
        if self.min_linear_speed < 0.0:
            raise ValueError("min_linear_speed cannot be negative.")
        if self.min_linear_speed > self.max_linear_speed:
            raise ValueError("min_linear_speed cannot exceed max_linear_speed.")
        if self.triangle_hold_seconds <= 0.0:
            raise ValueError("triangle_hold_seconds must be positive.")

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

        button_indices = {
            self.button_x,
            self.button_circle,
            self.button_square,
            self.button_triangle,
            self.button_l1,
            self.button_r1,
        }
        if len(button_indices) != 6 or min(button_indices) < 0:
            raise ValueError("All six button indices must be unique and non-negative.")

    @property
    def selected_mode(self) -> str:
        """Return the currently selected trajectory mode."""
        return self.trajectory_modes[self.mode_index]

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

    def _joy_callback(self, message: Joy) -> None:
        buttons = list(message.buttons)
        required_index = max(
            self.button_x,
            self.button_circle,
            self.button_square,
            self.button_triangle,
            self.button_l1,
            self.button_r1,
        )
        if len(buttons) <= required_index:
            self.get_logger().error(
                f"Joy message has {len(buttons)} buttons, but index {required_index} "
                "is required.",
                throttle_duration_sec=2.0,
            )
            return

        if not self.previous_buttons:
            self.previous_buttons = [0] * len(buttons)
        elif len(self.previous_buttons) < len(buttons):
            self.previous_buttons.extend([0] * (len(buttons) - len(self.previous_buttons)))

        manual_now = bool(buttons[self.button_l1] or buttons[self.button_r1])
        if manual_now:
            if not self.manual_buttons_down:
                self._enter_manual_override()
            self.manual_buttons_down = True
            self.previous_buttons = buttons
            return

        if self.manual_buttons_down and not manual_now:
            self.manual_buttons_down = False
            self._set_state(
                ControllerState.IDLE
                if self.home_x is not None
                else ControllerState.WAITING_FOR_HOME
            )
            self._publish_stop(repetitions=3)
            self.get_logger().info("Manual override released. Autonomous mode is idle.")

        triangle_rising = self._is_rising(buttons, self.button_triangle)
        triangle_falling = self._is_falling(buttons, self.button_triangle)

        if triangle_rising:
            self.triangle_is_down = True
            self.triangle_pressed_at = time.monotonic()
            self.triangle_hold_triggered = False
            self._cancel_autonomy("Triangle pressed: immediate cancel.")

        if triangle_falling:
            self.triangle_is_down = False
            self.triangle_pressed_at = None
            if (
                self.triangle_hold_triggered
                and self.return_requires_hold
                and self.state == ControllerState.RETURNING_HOME
            ):
                self._cancel_autonomy("Triangle released: return-to-home stopped.")
            self.triangle_hold_triggered = False

        if self._is_rising(buttons, self.button_square):
            self._handle_set_home()

        if self._is_rising(buttons, self.button_circle):
            self._handle_change_mode()

        if self._is_rising(buttons, self.button_x):
            self._handle_start()

        self.previous_buttons = buttons

    def _is_rising(self, buttons: Sequence[int], index: int) -> bool:
        return bool(buttons[index]) and not bool(self.previous_buttons[index])

    def _is_falling(self, buttons: Sequence[int], index: int) -> bool:
        return not bool(buttons[index]) and bool(self.previous_buttons[index])

    def _enter_manual_override(self) -> None:
        self._clear_mission()
        self._publish_stop(repetitions=3)
        self._set_state(ControllerState.MANUAL_OVERRIDE)
        self.get_logger().warning(
            "Manual override active. Any automatic mission was cancelled."
        )

    def _handle_set_home(self) -> None:
        if self.state in {ControllerState.RUNNING, ControllerState.RETURNING_HOME}:
            self.get_logger().warning("Square ignored while autonomy is active.")
            return
        if not self._odometry_is_ready():
            self.get_logger().warning("Cannot set home: valid odometry is not available.")
            return

        self.home_x = self.current_x
        self.home_y = self.current_y
        self.home_yaw = self.current_yaw
        self._clear_mission()
        self._set_state(ControllerState.IDLE)
        self.get_logger().info(
            "Home set from current odometry pose: "
            f"x={self.home_x:.3f}, y={self.home_y:.3f}, "
            f"yaw={math.degrees(self.home_yaw):.1f} deg."
        )

    def _handle_change_mode(self) -> None:
        if self.state in {ControllerState.RUNNING, ControllerState.RETURNING_HOME}:
            self.get_logger().warning("Circle ignored while autonomy is active.")
            return
        self.mode_index = (self.mode_index + 1) % len(self.trajectory_modes)
        self.get_logger().info(f"Trajectory mode selected: {self.selected_mode}.")
        if self.selected_mode == "inverse":
            self.get_logger().warning(
                "Inverse mode first transits directly to the far endpoint, then "
                "follows the horizontal serpentine backward to home."
            )
        self._publish_status()

    def _handle_start(self) -> None:
        if self.state in {ControllerState.RUNNING, ControllerState.RETURNING_HOME}:
            self.get_logger().info("X ignored because autonomy is already active.")
            return
        if self.state == ControllerState.MANUAL_OVERRIDE:
            self.get_logger().warning("X ignored while L1/R1 manual override is active.")
            return
        if self.home_x is None or self.home_y is None or self.home_yaw is None:
            self.get_logger().warning("Press Square first to define home.")
            return
        if not self._odometry_is_ready():
            self.get_logger().warning("Cannot start: odometry is unavailable or stale.")
            return

        self.mission = self._create_selected_mission()
        self.target_index = 0
        self.dwell_until = None
        self.last_phase = None
        self._set_state(ControllerState.RUNNING)
        self.get_logger().info(
            f"Mission started: mode={self.selected_mode}, laps={self.laps}, "
            f"targets={len(self.mission)}."
        )

    def _create_selected_mission(self) -> List[MissionWaypoint]:
        assert self.home_x is not None
        assert self.home_y is not None
        assert self.home_yaw is not None

        local_path = build_path(
            trajectory=self.selected_mode,
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

        if self.selected_mode == "inverse":
            return build_inverse_mission(
                odom_path,
                home_x=self.home_x,
                home_y=self.home_y,
                home_yaw=self.home_yaw,
                laps=self.laps,
                go_home_first=self.go_home_first,
                dwell_seconds=self.dwell_seconds,
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

    def _start_return_home(self) -> None:
        if self.home_x is None or self.home_y is None or self.home_yaw is None:
            self.get_logger().warning("Cannot return home: home has not been set.")
            return
        if not self._odometry_is_ready():
            self.get_logger().warning("Cannot return home: odometry is unavailable.")
            return

        self.mission = [
            MissionWaypoint(
                x=self.home_x,
                y=self.home_y,
                phase="button_return_home",
                lap=0,
                dwell_seconds=0.0,
                required_yaw=self.home_yaw,
            )
        ]
        self.target_index = 0
        self.dwell_until = None
        self.last_phase = None
        self.triangle_hold_triggered = True
        self._set_state(ControllerState.RETURNING_HOME)
        hold_text = (
            " Keep Triangle held to continue."
            if self.return_requires_hold
            else " The return will continue after release."
        )
        self.get_logger().warning("Return-to-home started." + hold_text)

    def _control_loop(self) -> None:
        if self.manual_buttons_down or self.state == ControllerState.MANUAL_OVERRIDE:
            return

        if (
            self.triangle_is_down
            and not self.triangle_hold_triggered
            and self.triangle_pressed_at is not None
            and time.monotonic() - self.triangle_pressed_at >= self.triangle_hold_seconds
        ):
            self._start_return_home()

        if self.state not in {
            ControllerState.RUNNING,
            ControllerState.RETURNING_HOME,
        }:
            return

        if (
            self.state == ControllerState.RETURNING_HOME
            and self.return_requires_hold
            and not self.triangle_is_down
        ):
            self._cancel_autonomy("Return-to-home requires Triangle to remain held.")
            return

        if not self._odometry_is_ready():
            self._publish_stop()
            self.get_logger().error(
                "Odometry timeout. Robot stopped.",
                throttle_duration_sec=2.0,
            )
            return

        if self.target_index >= len(self.mission):
            self._finish_mission()
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
            self.get_logger().info(
                f"Phase: {target.phase} | lap {target.lap}/{self.laps}."
            )

        assert self.current_x is not None
        assert self.current_y is not None
        assert self.current_yaw is not None

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
            f"phase={target.phase} | x={target.x:.2f}, y={target.y:.2f}."
        )
        if target.dwell_seconds > 0.0:
            self.dwell_until = time.monotonic() + target.dwell_seconds
        else:
            self.target_index += 1

    def _finish_mission(self) -> None:
        was_returning = self.state == ControllerState.RETURNING_HOME
        self._publish_stop(repetitions=10)
        self._clear_mission()
        self._set_state(ControllerState.IDLE)
        if was_returning:
            self.get_logger().info("Home reached. The Jackal is stopped.")
        else:
            self.get_logger().info("Mission completed. The Jackal is stopped at home.")

    def _cancel_autonomy(self, reason: str) -> None:
        if self.state in {ControllerState.RUNNING, ControllerState.RETURNING_HOME}:
            self.get_logger().warning(reason)
        self._clear_mission()
        self._publish_stop(repetitions=10)
        if self.state != ControllerState.MANUAL_OVERRIDE:
            self._set_state(
                ControllerState.IDLE
                if self.home_x is not None
                else ControllerState.WAITING_FOR_HOME
            )

    def _clear_mission(self) -> None:
        self.mission = []
        self.target_index = 0
        self.dwell_until = None
        self.last_phase = None

    def _odometry_is_ready(self) -> bool:
        return (
            self.current_x is not None
            and self.current_y is not None
            and self.current_yaw is not None
            and self.last_odom_time is not None
            and time.monotonic() - self.last_odom_time <= self.odom_timeout
        )

    def _set_state(self, state: ControllerState) -> None:
        if self.state != state:
            self.state = state
            self.get_logger().info(f"State: {self.state.value}")
            self._publish_status()

    def _publish_status(self) -> None:
        home_text = "set" if self.home_x is not None else "unset"
        message = String()
        message.data = (
            f"state={self.state.value};mode={self.selected_mode};home={home_text};"
            f"target={self.target_index}/{len(self.mission)}"
        )
        self.status_publisher.publish(message)

    def _publish_stop(self, repetitions: int = 1) -> None:
        stop = Twist()
        for _ in range(repetitions):
            self.cmd_publisher.publish(stop)

    def _on_parameters_changed(
        self,
        parameters: List[Parameter],
    ) -> SetParametersResult:
        non_dynamic = {
            "cmd_vel_topic",
            "odom_topic",
            "joy_topic",
            "status_topic",
            "trajectory_modes",
            "initial_mode",
            "control_rate",
        }
        for parameter in parameters:
            if parameter.name in non_dynamic:
                return SetParametersResult(
                    successful=False,
                    reason=f"{parameter.name} requires a node restart.",
                )

        mission_shape = {
            "return_mode",
            "laps",
            "go_home_first",
            "columns",
            "rows",
            "spacing_x",
            "spacing_y",
            "dwell_seconds",
        }
        if self.state in {ControllerState.RUNNING, ControllerState.RETURNING_HOME}:
            for parameter in parameters:
                if parameter.name in mission_shape:
                    return SetParametersResult(
                        successful=False,
                        reason=f"{parameter.name} can only change while IDLE.",
                    )

        prospective: Dict[str, object] = {
            "return_mode": self.return_mode,
            "laps": self.laps,
            "go_home_first": self.go_home_first,
            "columns": self.columns,
            "rows": self.rows,
            "spacing_x": self.spacing_x,
            "spacing_y": self.spacing_y,
            "dwell_seconds": self.dwell_seconds,
            "button_x": self.button_x,
            "button_circle": self.button_circle,
            "button_square": self.button_square,
            "button_triangle": self.button_triangle,
            "button_l1": self.button_l1,
            "button_r1": self.button_r1,
            "triangle_hold_seconds": self.triangle_hold_seconds,
            "return_requires_hold": self.return_requires_hold,
            "max_linear_speed": self.max_linear_speed,
            "min_linear_speed": self.min_linear_speed,
            "max_angular_speed": self.max_angular_speed,
            "linear_gain": self.linear_gain,
            "angular_gain": self.angular_gain,
            "position_tolerance": self.position_tolerance,
            "yaw_tolerance_deg": math.degrees(self.yaw_tolerance),
            "turn_in_place_angle_deg": math.degrees(self.turn_in_place_angle),
            "odom_timeout": self.odom_timeout,
        }
        for parameter in parameters:
            if parameter.name in prospective:
                prospective[parameter.name] = parameter.value

        try:
            self._validate_prospective_parameters(prospective)
        except ValueError as exc:
            return SetParametersResult(successful=False, reason=str(exc))

        for parameter in parameters:
            self._apply_dynamic_parameter(parameter)

        return SetParametersResult(successful=True)

    def _validate_prospective_parameters(self, values: Dict[str, object]) -> None:
        if str(values["return_mode"]) not in {"none", "reverse"}:
            raise ValueError("return_mode must be none or reverse.")
        if int(values["laps"]) < 1:
            raise ValueError("laps must be at least 1.")
        if int(values["laps"]) > 1 and str(values["return_mode"]) != "reverse":
            raise ValueError("laps > 1 requires return_mode=reverse.")
        if int(values["columns"]) < 1 or int(values["rows"]) < 1:
            raise ValueError("columns and rows must be at least 1.")
        if float(values["spacing_x"]) <= 0.0 or float(values["spacing_y"]) <= 0.0:
            raise ValueError("spacing values must be positive.")
        if float(values["dwell_seconds"]) < 0.0:
            raise ValueError("dwell_seconds cannot be negative.")
        if float(values["triangle_hold_seconds"]) <= 0.0:
            raise ValueError("triangle_hold_seconds must be positive.")
        if float(values["min_linear_speed"]) < 0.0:
            raise ValueError("min_linear_speed cannot be negative.")
        if float(values["min_linear_speed"]) > float(values["max_linear_speed"]):
            raise ValueError("min_linear_speed cannot exceed max_linear_speed.")

        for name in (
            "max_linear_speed",
            "max_angular_speed",
            "linear_gain",
            "angular_gain",
            "position_tolerance",
            "yaw_tolerance_deg",
            "turn_in_place_angle_deg",
            "odom_timeout",
        ):
            if float(values[name]) <= 0.0:
                raise ValueError(f"{name} must be positive.")

        button_names = (
            "button_x",
            "button_circle",
            "button_square",
            "button_triangle",
            "button_l1",
            "button_r1",
        )
        button_indices = [int(values[name]) for name in button_names]
        if min(button_indices) < 0 or len(set(button_indices)) != len(button_indices):
            raise ValueError("Button indices must be unique and non-negative.")

    def _apply_dynamic_parameter(self, parameter: Parameter) -> None:
        name = parameter.name
        value = parameter.value
        direct_attributes = {
            "return_mode",
            "laps",
            "go_home_first",
            "columns",
            "rows",
            "spacing_x",
            "spacing_y",
            "dwell_seconds",
            "button_x",
            "button_circle",
            "button_square",
            "button_triangle",
            "button_l1",
            "button_r1",
            "triangle_hold_seconds",
            "return_requires_hold",
            "max_linear_speed",
            "min_linear_speed",
            "max_angular_speed",
            "linear_gain",
            "angular_gain",
            "position_tolerance",
            "odom_timeout",
        }
        if name in direct_attributes:
            setattr(self, name, value)
        elif name == "yaw_tolerance_deg":
            self.yaw_tolerance = math.radians(float(value))
        elif name == "turn_in_place_angle_deg":
            self.turn_in_place_angle = math.radians(float(value))

    def stop(self) -> None:
        """Publish repeated zero velocity commands before shutdown."""
        self._publish_stop(repetitions=10)


def main(args=None) -> None:
    rclpy.init(args=args)
    node: Optional[JoystickTrajectoryController] = None
    try:
        node = JoystickTrajectoryController()
        rclpy.spin(node)
    except KeyboardInterrupt:
        if node is not None:
            node.get_logger().info("Interrupted by user. Stopping Jackal.")
    except Exception as exc:  # noqa: BLE001
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
