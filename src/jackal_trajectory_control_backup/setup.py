from glob import glob
from setuptools import find_packages, setup

package_name = "jackal_trajectory_control"

setup(
    name=package_name,
    version="0.2.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml", "README.md"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
        (f"share/{package_name}/config", glob("config/*.yaml")),
        (f"share/{package_name}/docs", glob("docs/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Edy Paz",
    maintainer_email="maintainer@example.com",
    description=(
        "Joystick-triggered closed-loop serpentine trajectories for Clearpath Jackal."
    ),
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "trajectory_follower = jackal_trajectory_control.trajectory_follower:main",
            "joystick_trajectory_controller = "
            "jackal_trajectory_control.joystick_trajectory_controller:main",
        ],
    },
)
