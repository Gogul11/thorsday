from pathlib import Path
import math
from typing import Dict
from langchain_core.tools import tool

@tool
def calculate_projectile_metrics(initial_velocity: float, launch_angle_degrees: float, gravity: float = 9.81) -> Dict[str, float]:
    """Calculate projectile range, peak height, and total flight time.
    
    Args:
        initial_velocity: Initial speed in meters per second.
        launch_angle_degrees: Launch angle above the horizontal in degrees.
        gravity: Acceleration due to gravity in m/s² (default 9.81).
    
    Returns:
        A dictionary with keys 'range', 'max_height', and 'total_time' containing the respective values.
    """
    theta = math.radians(launch_angle_degrees)
    vx = initial_velocity * math.cos(theta)
    vy = initial_velocity * math.sin(theta)
    total_time = (2 * vy) / gravity
    max_height = (vy ** 2) / (2 * gravity)
    range_distance = vx * total_time
    return {"range": range_distance, "max_height": max_height, "total_time": total_time}

@tool
def save_trajectory_summary(file_path: str, metrics: Dict[str, float]) -> str:
    """Write the projectile metrics to a text file.
    
    Args:
        file_path: Full path to the output text file.
        metrics: Dictionary containing 'range', 'max_height', and 'total_time'.
    
    Returns:
        Confirmation message indicating successful write.
    """
    path = Path(file_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "Projectile Simulation Summary:",
        f"Range (m): {metrics.get('range', 0):.3f}",
        f"Maximum Height (m): {metrics.get('max_height', 0):.3f}",
        f"Total Flight Time (s): {metrics.get('total_time', 0):.3f}",
    ]
    path.write_text("\n".join(lines))
    return f"Summary written to {path}"

PROJECTILE_TOOLS = [calculate_projectile_metrics, save_trajectory_summary]
