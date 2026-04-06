import asyncio
import httpx
import re
import gradio as gr
from mcp.server.fastmcp import FastMCP

# ============================================================
#                   GLOBAL CONSTANTS & SETUP
# ============================================================

API_URL_US = "https://api.weather.gov"
USER_AGENT = "weather-server-global/4.0"

mcp = FastMCP("Global Weather Service")
print("✅ Global Weather MCP Server is running...")


# ============================================================
#            WEATHER CODE MAPPING (HUMAN-FRIENDLY)
# ============================================================

WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle (dense)",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain (heavy)",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Severe thunderstorm with hail"
}

RAIN_CODES = {51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99}


# ============================================================
#                   UTILITY FUNCTIONS
# ============================================================

def is_in_usa(lat: float, lon: float) -> bool:
    return 24 <= lat <= 49 and -125 <= lon <= -66


async def fetch_json(url: str, headers=None):
    if headers is None:
        headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def geocode_place(place: str):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": place, "format": "json", "limit": 1}
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    if not data:
        return None, None
    return float(data[0]["lat"]), float(data[0]["lon"])


# ============================================================
#            NLP: LOCATION EXTRACTION FROM QUESTIONS
# ============================================================

KNOWN_CITIES = {
    "Pune", "Mumbai", "Delhi", "Bangalore", "Bengaluru", "Hyderabad",
    "Chennai", "Kolkata", "Nagpur", "Nashik", "Goa", "Durgapur",
    "New York", "Los Angeles", "Chicago", "San Francisco", "Houston",
    "London", "Paris", "Tokyo"
}

async def extract_place_from_question(question: str):
    cleaned = re.sub(r"[^\w\s]", "", question)
    tokens = cleaned.split()

    # Check known cities first
    for token in tokens:
        if token in KNOWN_CITIES:
            return token

    # Multi-word city support
    for i in range(len(tokens) - 1):
        combined = tokens[i] + " " + tokens[i + 1]
        if combined in KNOWN_CITIES:
            return combined

    # Fallback: last capitalized word
    capitals = [t for t in tokens if t[0].isupper()]
    if capitals:
        return capitals[-1]

    return None


# ============================================================
#       WEATHER FETCHERS — US (NWS) & GLOBAL (OPEN-METEO)
# ============================================================

async def fetch_us_forecast(lat: float, lon: float):
    point_url = f"{API_URL_US}/points/{lat},{lon}"
    metadata = await fetch_json(point_url)
    forecast_url = metadata["properties"]["forecast"]
    forecast = await fetch_json(forecast_url)
    period = forecast["properties"]["periods"][0]

    return (
        f"**{period['name']}** — {period['detailedForecast']}"
    )


async def fetch_global_forecast(lat: float, lon: float):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current_weather=true"
        "&hourly=precipitation_probability"
    )

    data = await fetch_json(url)
    cw = data.get("current_weather", {})
    hourly = data.get("hourly", {})

    rain_prob = None
    if "precipitation_probability" in hourly:
        try:
            rain_prob = hourly["precipitation_probability"][0]
        except:
            pass

    return {
        "lat": lat,
        "lon": lon,
        "temp": cw.get("temperature"),
        "wind": cw.get("windspeed"),
        "weathercode": cw.get("weathercode"),
        "rain_prob": rain_prob
    }


# ============================================================
#           SMART WEATHER ANSWERING SYSTEM
# ============================================================

def generate_weather_answer(place, forecast):
    lat = forecast["lat"]
    lon = forecast["lon"]
    temp = forecast["temp"]
    wind = forecast["wind"]
    code = forecast["weathercode"]
    rain_prob = forecast["rain_prob"]

    condition = WEATHER_CODE_MAP.get(code, "Unknown")

    # Rain logic
    will_rain = code in RAIN_CODES or (rain_prob and rain_prob > 50)

    if will_rain:
        rain_line = f"🌧 **Yes, it is likely to rain today in {place}.**"
        if rain_prob is not None:
            rain_line += f" (Rain probability: {rain_prob}%)"
    else:
        rain_line = f"🌤 **No, it is not expected to rain today in {place}.**"
        if rain_prob is not None:
            rain_line += f" (Chance of rain: {rain_prob}%)"

    summary = (
        f"{rain_line}\n\n"
        f"**Current Conditions:**\n"
        f"- Sky: {condition}\n"
        f"- Temperature: {temp}°C\n"
        f"- Wind: {wind} km/h\n"
        f"- Coordinates: ({lat}, {lon})\n"
    )

    # Smart comments
    if temp is not None:
        if temp >= 35:
            summary += "\n🔥 It's very hot today. Stay hydrated!"
        elif temp <= 10:
            summary += "\n❄ It's cold today. Wear warm clothes!"

    if "cloud" in condition.lower() or code in {2, 3}:
        summary += "\n☁ Expect cloudy conditions."

    if will_rain:
        summary += "\n🌂 You may want to carry an umbrella."

    return summary


# ============================================================
#                 UNIFIED MCP FORECAST WRAPPER
# ============================================================

@mcp.tool()
async def get_forecast(lat: float, lon: float) -> str:
    if is_in_usa(lat, lon):
        return await fetch_us_forecast(lat, lon)
    return generate_weather_answer("Location", await fetch_global_forecast(lat, lon))


@mcp.tool()
async def get_alerts(state: str) -> str:
    url = f"{API_URL_US}/alerts/active?area={state.upper()}"
    data = await fetch_json(url)
    alerts = data.get("features", [])
    if not alerts:
        return f"No active alerts for {state.upper()}."

    out = f"**Active Alerts for {state.upper()}:**\n\n"
    for alert in alerts:
        props = alert["properties"]
        out += f"- **{props['event']}**: {props['headline']}\n"
    return out


# ============================================================
#        NATURAL LANGUAGE WEATHER QUESTION HANDLER
# ============================================================

async def parse_weather_question(question: str):
    place = await extract_place_from_question(question)
    if not place:
        return f"Could not extract a location from your question."

    lat, lon = await geocode_place(place)
    if lat is None:
        return f"Could not geocode location: {place}"

    if is_in_usa(lat, lon):
        forecast_us = await fetch_us_forecast(lat, lon)
        return f"**User Question:** {question}\n\n**Forecast for {place}:**\n{forecast_us}"

    forecast = await fetch_global_forecast(lat, lon)
    answer = generate_weather_answer(place, forecast)

    return f"**User Question:** {question}\n\n{answer}"


# ============================================================
#                  ASYNC GRADIO UI HANDLERS
# ============================================================

async def ui_forecast(lat, lon):
    return await get_forecast(lat, lon)

async def ui_alerts(state):
    return await get_alerts(state)

async def ui_weather_by_place(place):
    lat, lon = await geocode_place(place)
    if lat is None:
        return f"Could not geocode '{place}'."
    return await get_forecast(lat, lon)

async def ui_weather_question(question):
    return await parse_weather_question(question)


# ============================================================
#                       GRADIO UI
# ============================================================

forecast_interface = gr.Interface(
    fn=ui_forecast,
    inputs=[gr.Number(label="Latitude"), gr.Number(label="Longitude")],
    outputs="text",
    title="Weather Forecast by Coordinates"
)

alerts_interface = gr.Interface(
    fn=ui_alerts,
    inputs=gr.Textbox(label="US State (e.g., CA, TX, FL)"),
    outputs="text",
    title="Weather Alerts (US Only)"
)

place_interface = gr.Interface(
    fn=ui_weather_by_place,
    inputs=gr.Textbox(label="Place Name (City, Landmark, etc.)"),
    outputs="text",
    title="Weather by Place Name"
)

question_interface = gr.Interface(
    fn=ui_weather_question,
    inputs=gr.Textbox(label="Ask a Natural-Language Weather Question"),
    outputs="text",
    title="Natural-Language Weather Questions",
    description="Examples: 'Will it rain today in Pune?', 'Is it hot in Mumbai?'"
)

demo = gr.TabbedInterface(
    [
        forecast_interface,
        alerts_interface,
        place_interface,
        question_interface
    ],
    tab_names=[
        "Forecast (Lat/Lon)",
        "Alerts (State)",
        "Weather by Place",
        "Ask a Weather Question"
    ]
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
