import json
import urllib.parse
import urllib.request
from logger import logger

WMO_WEATHER_CODES = {
    0: "clear skies",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snowfall",
    73: "moderate snowfall",
    75: "heavy snowfall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorms",
    96: "thunderstorms with slight hail",
    99: "thunderstorms with heavy hail"
}

def get_weather_description(code: int) -> str:
    return WMO_WEATHER_CODES.get(code, "fair")

def get_coordinates(city_name: str):
    """
    Fetches latitude, longitude, and resolved city name using Open-Meteo Geocoding API.
    """
    encoded_city = urllib.parse.quote(city_name.strip())
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=en&format=json"
    
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "DeeksVoiceAssistant/1.0"}
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
        results = data.get("results")
        if not results:
            return None
        first = results[0]
        return {
            "name": first.get("name"),
            "country": first.get("country", ""),
            "latitude": first.get("latitude"),
            "longitude": first.get("longitude")
        }

def get_weather(city_name: str = None) -> dict:
    """
    Fetches current conditions and today's forecast for the given city using Open-Meteo.
    Defaults to memory's default_city or 'Chennai' (Indian Standard Time) if not specified.
    Returns a dict containing resolved details and a natural speech summary, or error info.
    """
    try:
        if not city_name:
            from memory.memory import load_memory
            city_name = load_memory("default_city") or "Chennai"

        geo = get_coordinates(city_name)
        if not geo:
            logger.warning(f"Could not find coordinates for city: {city_name}")
            return {
                "success": False,
                "error": f"I couldn't find the location for {city_name}."
            }
            
        lat = geo["latitude"]
        lon = geo["longitude"]
        resolved_name = geo["name"]
        
        forecast_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,weather_code"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            f"&timezone=auto"
        )
        
        req = urllib.request.Request(
            forecast_url,
            headers={"User-Agent": "DeeksVoiceAssistant/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            
        current = data.get("current", {})
        daily = data.get("daily", {})
        
        current_temp = round(current.get("temperature_2m", 0))
        current_code = current.get("weather_code", 0)
        condition_desc = get_weather_description(current_code)
        
        rain_chances = daily.get("precipitation_probability_max", [0])
        chance_of_rain = rain_chances[0] if rain_chances else 0
        if chance_of_rain is None:
            chance_of_rain = 0
            
        # Format a natural sounding summary
        summary = (
            f"It's {current_temp} degrees and {condition_desc}, "
            f"with a {chance_of_rain}% chance of rain today in {resolved_name}."
        )
        
        return {
            "success": True,
            "city": resolved_name,
            "country": geo.get("country", ""),
            "temperature": current_temp,
            "condition": condition_desc,
            "chance_of_rain": chance_of_rain,
            "summary": summary
        }
        
    except Exception as e:
        logger.exception(f"Error fetching weather for '{city_name}': {e}")
        return {
            "success": False,
            "error": "I had trouble connecting to the weather service."
        }
