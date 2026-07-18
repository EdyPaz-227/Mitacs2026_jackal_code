"""Launch the Jackal trajectory follower with user-facing arguments."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    arguments = [
        DeclareLaunchArgument("robot_namespace", default_value="j100_0000"),
        DeclareLaunchArgument("trajectory", default_value="horizontal"),
        DeclareLaunchArgument("return_mode", default_value="none"),
        DeclareLaunchArgument("laps", default_value="1"),
        DeclareLaunchArgument("home_x", default_value="0.0"),
        DeclareLaunchArgument("home_y", default_value="0.0"),
        DeclareLaunchArgument("home_yaw_deg", default_value="0.0"),
        DeclareLaunchArgument("go_home_first", default_value="true"),
        DeclareLaunchArgument("columns", default_value="8"),
        DeclareLaunchArgument("rows", default_value="5"),
        DeclareLaunchArgument("spacing_x", default_value="1.0"),
        DeclareLaunchArgument("spacing_y", default_value="1.0"),
        DeclareLaunchArgument("dwell_seconds", default_value="0.5"),
        DeclareLaunchArgument("cmd_vel_topic", default_value="cmd_vel"),
        DeclareLaunchArgument("odom_topic", default_value=""),
        DeclareLaunchArgument("max_linear_speed", default_value="0.30"),
        DeclareLaunchArgument("max_angular_speed", default_value="0.70"),
        DeclareLaunchArgument("position_tolerance", default_value="0.08"),
    ]

    node = Node(
        package="jackal_trajectory_control",
        executable="trajectory_follower",
        name="trajectory_follower",
        namespace=LaunchConfiguration("robot_namespace"),
        output="screen",
        emulate_tty=True,
        parameters=[
            {
                "trajectory": LaunchConfiguration("trajectory"),
                "return_mode": LaunchConfiguration("return_mode"),
                "laps": ParameterValue(LaunchConfiguration("laps"), value_type=int),
                "home_x": ParameterValue(LaunchConfiguration("home_x"), value_type=float),
                "home_y": ParameterValue(LaunchConfiguration("home_y"), value_type=float),
                "home_yaw_deg": ParameterValue(
                    LaunchConfiguration("home_yaw_deg"), value_type=float
                ),
                "go_home_first": ParameterValue(
                    LaunchConfiguration("go_home_first"), value_type=bool
                ),
                "columns": ParameterValue(LaunchConfiguration("columns"), value_type=int),
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
                "cmd_vel_topic": LaunchConfiguration("cmd_vel_topic"),
                "odom_topic": LaunchConfiguration("odom_topic"),
                "max_linear_speed": ParameterValue(
                    LaunchConfiguration("max_linear_speed"), value_type=float
                ),
                "max_angular_speed": ParameterValue(
                    LaunchConfiguration("max_angular_speed"), value_type=float
                ),
                "position_tolerance": ParameterValue(
                    LaunchConfiguration("position_tolerance"), value_type=float
                ),
            }
        ],
    )

    return LaunchDescription(arguments + [node])
