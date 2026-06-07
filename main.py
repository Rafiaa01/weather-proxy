import httpx
import os
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone

load_dotenv()

app = FastAPI(
    title="Weather Proxy API",
    description="A proxy API that fetches weather data from OpenWeatherMap",
    version="1.0.0",
)

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
WEATHER_BASE_URL = os.getenv("WEATHER_BASE_URL", "https://api.openweathermap.org/data/2.5")


class Temperature(BaseModel):
    current: float
    feels_like: float
    min: float
    max: float
    unit: str = "Celsius"

class Wind(BaseModel):
    speed: str
    direction: str

class Condition(BaseModel):
    main: str
    description: str

class WeatherData(BaseModel):
    city: str
    country: str
    temperature: Temperature
    humidity: str
    wind: Wind
    conditions: List[Condition]
    visibility: str
    timestamp: str

class WeatherResponse(BaseModel):
    success: bool
    data: WeatherData


async def fetch_weather(city: str) -> dict:
    if not WEATHER_API_KEY:
        raise HTTPException(status_code=500, detail="WEATHER_API_KEY is not set")
    params = {"q": city, "appid": WEATHER_API_KEY, "units": "metric"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{WEATHER_BASE_URL}/weather", params=params)
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Could not reach weather service.")
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="City not found.")
    if response.status_code == 429:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="External API error.")
    return response.json()


def format_weather(data: dict) -> WeatherData:
    return WeatherData(
        city=data["name"],
        country=data["sys"]["country"],
        temperature=Temperature(
            current=data["main"]["temp"],
            feels_like=data["main"]["feels_like"],
            min=data["main"]["temp_min"],
            max=data["main"]["temp_max"],
        ),
        humidity=str(data["main"]["humidity"]) + "%",
        wind=Wind(speed=str(data["wind"]["speed"]) + " m/s", direction=str(data["wind"].get("deg", "N/A"))),
        conditions=[Condition(main=w["main"], description=w["description"]) for w in data["weather"]],
        visibility=str(round(data.get("visibility", 0) / 1000, 1)) + " km",
        timestamp=datetime.fromtimestamp(data["dt"], tz=timezone.utc).isoformat(),
    )


@app.get("/", tags=["Health"])
async def root():
    return {"message": "Weather Proxy API is running", "docs": "/docs"}

@app.get("/weather/london", response_model=WeatherResponse, tags=["Weather"])
async def get_london_weather():
    """Fetch current weather for London."""
    raw = await fetch_weather("London")
    return WeatherResponse(success=True, data=format_weather(raw))

@app.get("/weather/{city}", response_model=WeatherResponse, tags=["Weather"])
async def get_city_weather(city: str):
    """Fetch current weather for any city."""
    raw = await fetch_weather(city)
    return WeatherResponse(success=True, data=format_weather(raw))
