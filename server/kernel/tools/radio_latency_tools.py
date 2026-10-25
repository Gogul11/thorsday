from langchain_core.tools import tool

@tool
def calculate_round_trip_time(distance_km: float) -> dict:
    """Calculate the round‑trip radio signal travel time for a given distance.

    Args:
        distance_km: Separation distance between two points in kilometers.

    Returns:
        A dictionary with keys:
            - "minutes": whole minutes of the round‑trip travel time.
            - "seconds": remaining seconds (float) after minutes are accounted for.
    """
    speed_of_light_km_s = 299_792  # km per second
    one_way_seconds = distance_km / speed_of_light_km_s
    round_trip_seconds = 2 * one_way_seconds
    minutes = int(round_trip_seconds // 60)
    seconds = round_trip_seconds - minutes * 60
    return {"minutes": minutes, "seconds": seconds}

RADIO_LATENCY_TOOLS = [calculate_round_trip_time]