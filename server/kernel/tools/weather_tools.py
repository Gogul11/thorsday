"""Weather tools for AgentOS.

Fetches real-time weather and forecasts worldwide using the free Open-Meteo API
(requires no API key).
"""

import json
import urllib.parse
import urllib.request
from langchain_core.tools import tool
from logger import logger

# WMO Weather interpretation codes (WW)
# Reference: https://open-meteo.com/en/docs
WMO_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _geocode_city(city: str) -> dict | None:
    """Geocode a city name to latitude, longitude, and display name."""
    encoded_city = urllib.parse.quote(city.strip())
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=en&format=json"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AgentOS-WeatherAgent/1.0"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results")
        if results and len(results) > 0:
            return results[0]
    return None


@tool
def get_current_weather(city: str) -> str:
    """Get the current live weather conditions for any city worldwide.

    Args:
        city: The name of the city (e.g., 'London', 'Tokyo', 'San Francisco', 'Paris').

    Returns:
        A detailed summary of current temperature, apparent temperature,
        weather conditions, humidity, wind speed, and precipitation.
    """
    try:
        location = _geocode_city(city)
        if not location:
            return f"Could not find geographic coordinates for city '{city}'. Please check the city name."

        name = location.get("name", city)
        country = location.get("country", "")
        admin1 = location.get("admin1", "")
        location_str = f"{name}, {admin1 + ', ' if admin1 else ''}{country}".strip()
        lat = location["latitude"]
        lon = location["longitude"]

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&"
            f"timezone=auto"
        )

        req = urllib.request.Request(
            weather_url,
            headers={"User-Agent": "AgentOS-WeatherAgent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            weather_data = json.loads(resp.read().decode("utf-8"))

        current = weather_data.get("current", {})
        temp_c = current.get("temperature_2m", "N/A")
        temp_f = round(temp_c * 9 / 5 + 32, 1) if isinstance(temp_c, (int, float)) else "N/A"
        feels_like_c = current.get("apparent_temperature", "N/A")
        feels_like_f = round(feels_like_c * 9 / 5 + 32, 1) if isinstance(feels_like_c, (int, float)) else "N/A"
        humidity = current.get("relative_humidity_2m", "N/A")
        precip = current.get("precipitation", 0.0)
        wind_speed = current.get("wind_speed_10m", "N/A")
        code = current.get("weather_code", -1)
        condition = WMO_WEATHER_CODES.get(code, "Unknown condition")

        return (
            f"Current Weather for {location_str}:\n"
            f"- Condition: {condition}\n"
            f"- Temperature: {temp_c}°C ({temp_f}°F)\n"
            f"- Feels Like: {feels_like_c}°C ({feels_like_f}°F)\n"
            f"- Relative Humidity: {humidity}%\n"
            f"- Wind Speed: {wind_speed} km/h\n"
            f"- Precipitation: {precip} mm"
        )
    except Exception as exc:
        logger.exception("Error fetching current weather for %s: %s", city, exc)
        return f"Error retrieving current weather for '{city}': {exc}"


@tool
def get_weather_forecast(city: str, days: int = 3) -> str:
    """Get the multi-day weather forecast for any city worldwide.

    Args:
        city: The name of the city (e.g., 'New York', 'Sydney', 'Berlin').
        days: Number of forecast days to retrieve (between 1 and 7, defaults to 3).

    Returns:
        Daily weather forecast including maximum and minimum temperatures,
        expected weather condition, and precipitation sum.
    """
    days = max(1, min(days, 7))
    try:
        location = _geocode_city(city)
        if not location:
            return f"Could not find geographic coordinates for city '{city}'. Please check the city name."

        name = location.get("name", city)
        country = location.get("country", "")
        admin1 = location.get("admin1", "")
        location_str = f"{name}, {admin1 + ', ' if admin1 else ''}{country}".strip()
        lat = location["latitude"]
        lon = location["longitude"]

        forecast_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum&"
            f"timezone=auto&forecast_days={days}"
        )

        req = urllib.request.Request(
            forecast_url,
            headers={"User-Agent": "AgentOS-WeatherAgent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            forecast_data = json.loads(resp.read().decode("utf-8"))

        daily = forecast_data.get("daily", {})
        dates = daily.get("time", [])
        codes = daily.get("weather_code", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precips = daily.get("precipitation_sum", [])

        lines = [f"{days}-Day Weather Forecast for {location_str}:"]
        for i in range(len(dates)):
            date = dates[i]
            cond = WMO_WEATHER_CODES.get(codes[i], "Unknown") if i < len(codes) else "Unknown"
            max_t = max_temps[i] if i < len(max_temps) else "N/A"
            min_t = min_temps[i] if i < len(min_temps) else "N/A"
            rain = precips[i] if i < len(precips) else 0.0
            lines.append(
                f"- {date}: {cond} | High: {max_t}°C | Low: {min_t}°C | Rain: {rain} mm"
            )

        return "\n".join(lines)
    except Exception as exc:
        logger.exception("Error fetching weather forecast for %s: %s", city, exc)
        return f"Error retrieving weather forecast for '{city}': {exc}"

