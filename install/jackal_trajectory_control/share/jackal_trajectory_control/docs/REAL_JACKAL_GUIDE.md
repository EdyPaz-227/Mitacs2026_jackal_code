# Real Jackal J100-0751 quick guide

## Start manually

Always source the Clearpath environment first — it sets the ROS domain and
middleware. Use the exact same two lines in **every** terminal (launch, echo,
diagnostics); mixing environments makes nodes invisible to each other:

```bash
source /etc/clearpath/setup.bash
source ~/jackal_ws/install/setup.bash
ros2 launch jackal_trajectory_control joystick_trajectory.launch.py
```

The launch also starts a `joy_linux_node` on `joy_teleop/joy` (the platform
publisher on this robot stays silent). Disable it with `launch_joy:=false` if
the platform joystick driver is fixed later.

Expected state at startup: `WAITING_FOR_HOME`. The node publishes no motion
until X is pressed after home has been set.

## Button sequence

1. Drive the robot manually to the desired home pose.
2. Release L1/R1 and all sticks.
3. Press Square once to save home and grid orientation.
4. Press Circle to choose horizontal, vertical or inverse.
5. Press X once to start.
6. Press Triangle once for immediate cancellation.
7. Hold Triangle for one second to return directly to home. Keep it held until
   home is reached with the default safety configuration.
8. Press L1 or R1 at any time to take manual priority and cancel autonomy.

## Watch status

```bash
ros2 topic echo /j100_0751/trajectory/status
```

## Safe small test

```bash
ros2 launch jackal_trajectory_control joystick_trajectory.launch.py \
  columns:=2 rows:=2 spacing_x:=0.50 spacing_y:=0.50 \
  max_linear_speed:=0.10 max_angular_speed:=0.25 \
  dwell_seconds:=1.0
```

## Persistent tuning

Edit:

```text
~/jackal_ws/src/jackal_trajectory_control/config/joystick.yaml
```

Then rebuild and source:

```bash
cd ~/jackal_ws
colcon build --symlink-install
source install/setup.bash
```

Because the package is built with `--symlink-install`, Python source edits are
usually visible immediately, but rebuilding after configuration or launch-file
changes avoids confusion.

## Buttons do nothing? Check in this order

1. Same environment in every terminal (see "Start manually" above).
2. The robot runs THIS version: `cd ~/jackal_ws && colcon build --symlink-install
   && source install/setup.bash`, then relaunch.
3. Joy data actually flows:
   `ros2 topic echo /j100_0751/joy_teleop/joy` (press Square → `buttons[2]: 1`).
4. The controller is subscribed:
   `ros2 node info /j100_0751/joystick_trajectory_controller`.
5. Odometry is alive (Square needs it to set home):
   `ros2 topic hz /j100_0751/platform/odom/filtered`.
6. Controller reacts but robot does not move: check the command output with
   `ros2 topic echo /j100_0751/cmd_vel` and the twist mux priorities.
