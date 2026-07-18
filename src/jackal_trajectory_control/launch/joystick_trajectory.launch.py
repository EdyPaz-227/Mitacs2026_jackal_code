"""Launch the joystick-controlled Jackal trajectory node."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    default_config = PathJoinSubstitution(
        [FindPackageShare("jackal_trajectory_control"), "config", "joystick.yaml"]
    )

    arguments = [
        DeclareLaunchArgument("robot_namespace", default_value="j100_0751"),
        DeclareLaunchArgument("config_file", default_value=default_config),
        # The platform already runs a joy node on joy_teleop/joy; it looked
        # silent only because Fast DDS SHM data does not cross users (fixed by
        # the UDP-only profile in fastdds_udp_only.xml). A second joy publisher
        # interleaves button streams and can double-trigger edge detection, so
        # keep this off unless the platform joy is genuinely down.
        DeclareLaunchArgument(
            "launch_joy",
            default_value="false",
            description="Start a fallback joy_linux_node on joy_teleop/joy.",
        ),
        DeclareLaunchArgument("max_linear_speed", default_value="0.20"),
        DeclareLaunchArgument("max_angular_speed", default_value="0.40"),
        DeclareLaunchArgument("laps", default_value="1"),
        DeclareLaunchArgument("columns", default_value="8"),
        DeclareLaunchArgument("rows", default_value="5"),
        DeclareLaunchArgument("spacing_x", default_value="1.0"),
        DeclareLaunchArgument("spacing_y", default_value="1.0"),
        DeclareLaunchArgument("dwell_seconds", default_value="0.5"),
    ]

    node = Node(
        package="jackal_trajectory_control",
        executable="joystick_trajectory_controller",
        name="joystick_trajectory_controller",
        namespace=LaunchConfiguration("robot_namespace"),
        output="screen",
        emulate_tty=True,
        parameters=[
            LaunchConfiguration("config_file"),
            {
                "max_linear_speed": ParameterValue(
                    LaunchConfiguration("max_linear_speed"), value_type=float
                ),
                "max_angular_speed": ParameterValue(
                    LaunchConfiguration("max_angular_speed"), value_type=float
                ),
                "laps": ParameterValue(LaunchConfiguration("laps"), value_type=int),
                "columns": ParameterValue(
                    LaunchConfiguration("columns"), value_type=int
                ),
                "rows": ParameterValue(LaunchConfiguration("rows"), value_type=int),
                "spacing_x": ParameterValue(
                    LaunchConfiguration("spacing_x"), value_type=float
                ),
                "spacing_y": ParameterValue(
                    LaunchConfiguration("spacing_y"), value_type=float
                ),
                "dwell_seconds": ParameterValue(
                    LaunchConfiguration("dwell_seconds"), value_type=float
                ),
            },
        ],
    )

    joy_node = Node(
        package="joy_linux",
        executable="joy_linux_node",
        name="joy_linux_node",
        namespace=LaunchConfiguration("robot_namespace"),
        output="screen",
        condition=IfCondition(LaunchConfiguration("launch_joy")),
        remappings=[("joy", "joy_teleop/joy")],
    )

    return LaunchDescription(arguments + [node, joy_node])
