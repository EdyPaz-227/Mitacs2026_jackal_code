# Jackal Trajectory Control

ROS 2 Humble package for a Clearpath Jackal J100. Version 0.2 adds a
PlayStation-controller state machine while preserving the original direct
trajectory follower.

## Real-robot joystick behavior

The joystick node starts motionless and waits for commands:

| Button | Action |
|---|---|
| X (`buttons[0]`) | Start the selected trajectory |
| Circle (`buttons[1]`) | Cycle horizontal → vertical → inverse |
| Square (`buttons[2]`) | Store the current odometry pose as local home `(0,0,0)` |
| Triangle (`buttons[3]`) | Cancel immediately; hold for return-to-home |
| L1/R1 (`buttons[9]/[10]`) | Manual override with priority; cancels autonomy |

X is ignored while an automatic mission is running. Square and Circle are
ignored during autonomy. Releasing manual override leaves the controller idle;
it never resumes a cancelled mission automatically.

With `return_requires_hold: true`, Triangle must remain held during the direct
return-to-home motion. Releasing Triangle stops the robot immediately.

## Trajectory modes

- `horizontal`: row-wise serpentine, then exact reverse waypoint return.
- `vertical`: column-wise serpentine, then exact reverse waypoint return.
- `inverse`: direct transit to the far endpoint of the normal horizontal path,
  then the same horizontal waypoint sequence is followed backward to home.

The inverse transit is not obstacle-aware. Use it only in a clear room.

## Jackal J100-0751 topics

The supplied configuration resolves these relative names under namespace
`/j100_0751`:

- Command input: `/j100_0751/cmd_vel`
- Filtered odometry: `/j100_0751/platform/odom/filtered`
- Joystick: `/j100_0751/joy_teleop/joy`
- Status: `/j100_0751/trajectory/status`

`cmd_vel` is used as the autonomous input. The standard
`joy_teleop/cmd_vel` input remains separate, and L1/R1 also cancel this node's
mission to preserve manual priority.

## Build

```bash
mkdir -p ~/jackal_ws/src
cd ~/jackal_ws/src
# Copy the jackal_trajectory_control folder here.

cd ~/jackal_ws
source /opt/ros/humble/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

## Manual launch for the real robot

```bash
ros2 launch jackal_trajectory_control joystick_trajectory.launch.py
```

The launch also starts a `joy_linux_node` remapped to `joy_teleop/joy`, because
the platform joy publisher on j100_0751 stays silent. Pass `launch_joy:=false`
to rely on the platform driver instead.

The node does not move at launch. Press Square to set home, use Circle to choose
mode, then press X to start.

## Override launch values without editing Python

```bash
ros2 launch jackal_trajectory_control joystick_trajectory.launch.py \
  max_linear_speed:=0.15 \
  max_angular_speed:=0.30 \
  columns:=3 rows:=2 \
  spacing_x:=0.50 spacing_y:=0.50 \
  dwell_seconds:=1.0
```

Persistent defaults are stored in `config/joystick.yaml`.

Several values can also be changed while the node is running:

```bash
ros2 param set /j100_0751/joystick_trajectory_controller max_linear_speed 0.15
ros2 param set /j100_0751/joystick_trajectory_controller max_angular_speed 0.30
```

Grid dimensions, spacing, laps and dwell can only be changed while the node is
idle. Topic names and the control rate require restarting the node.

## First test recommendation

Do not begin with the full 8 × 5 m grid. Use a small 2 × 2 or 3 × 2 grid at
0.5 m spacing and conservative speed, with the robot in a clear area and a
person ready at the physical emergency stop.

## Legacy direct launch

The original simulation/direct follower remains available:

```bash
ros2 launch jackal_trajectory_control trajectory.launch.py \
  robot_namespace:=j100_0751 \
  trajectory:=horizontal return_mode:=reverse
```

This legacy node starts automatically after receiving odometry, so do not use
it for the controller-button workflow.
