from datetime import datetime
from logger import logger
from memory.memory import load_memory
from skills.weather_skill import get_weather
from skills.schedule_skill import get_schedule
from skills.news_skill import get_top_headlines

def get_daily_briefing() -> str:
    """
    Generates a consolidated, smooth daily briefing containing:
    1. Time-of-day greeting
    2. Current weather & rain chance
    3. Today's schedule / agenda
    4. Top 3 news headlines
    5. Closing sign-off
    """
    now = datetime.now()
    hour = now.hour
    
    if 5 <= hour < 12:
        greeting = "Good morning!"
    elif 12 <= hour < 17:
        greeting = "Good afternoon!"
    elif 17 <= hour < 22:
        greeting = "Good evening!"
    else:
        greeting = "Hello!"
        
    parts = [f"{greeting} Here is your daily briefing."]
    
    # 1. Weather
    city = load_memory("default_city") or "Chennai"
    try:
        weather_res = get_weather(city)
        if weather_res.get("success"):
            parts.append(weather_res["summary"])
    except Exception as e:
        logger.warning(f"Briefing: Error retrieving weather: {e}")
        
    # 2. Schedule
    try:
        schedule_text = get_schedule("today")
        parts.append(schedule_text)
    except Exception as e:
        logger.warning(f"Briefing: Error retrieving schedule: {e}")
        parts.append("I couldn't load today's schedule.")
        
    # 3. News (Top 3)
    try:
        news_res = get_top_headlines(limit=3)
        if news_res.get("success") and news_res.get("headlines"):
            headlines = news_res["headlines"][:3]
            ordinals = ["First", "Second", "Third"]
            news_items = [f"{ordinals[i]}, {h}" for i, h in enumerate(headlines)]
            parts.append("In the news: " + ". ".join(news_items) + ".")
    except Exception as e:
        logger.warning(f"Briefing: Error retrieving news: {e}")
        
    # 4. Sign-off
    if hour >= 17:
        parts.append("That's all for your briefing. Have a wonderful evening!")
    else:
        parts.append("That's all for your briefing. Have a wonderful day!")
        
    return " ".join(parts)
