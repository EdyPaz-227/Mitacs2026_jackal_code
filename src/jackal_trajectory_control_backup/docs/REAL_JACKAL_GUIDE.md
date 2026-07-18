# Real Jackal J100-0751 quick guide

## Start manually

```bash
source /opt/ros/humble/setup.bash
source ~/jackal_ws/install/setup.bash
ros2 launch jackal_trajectory_control joystick_trajectory.launch.py
```

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
