"""
India LIVE Weather App - Accuracy Version
- Search any village / town / city in India
- Asks 3 weather models (ECMWF, GFS, ICON) and shows their AVERAGE
- Shows how much the models agree (confidence)
- Shows exact latitude / longitude / elevation + "Verify on map" button
- Auto-refresh every 10 minutes, 5 day forecast
- Free data from Open-Meteo (no API key needed)
"""

import json
import threading
import tkinter as tk
import urllib.parse
import urllib.request
import webbrowser
from collections import Counter
from datetime import datetime

# ---------- settings ----------
BG, CARD, TEXT, MUTED, ACCENT = "#0f172a", "#1e293b", "#f1f5f9", "#94a3b8", "#38bdf8"
GREEN, YELLOW, RED = "#4ade80", "#facc15", "#f87171"
REFRESH_MINUTES = 10

# the weather models we ask (name shown on screen -> name used by the API)
MODELS = {"ECMWF": "ecmwf_ifs025", "GFS": "gfs_seamless", "ICON": "icon_seamless"}

CURRENT_KEYS = ["temperature_2m", "apparent_temperature", "relative_humidity_2m",
                "wind_speed_10m", "surface_pressure", "precipitation"]

# weather code -> (text, emoji)
CODES = {
    0: ("Clear sky", "☀️"), 1: ("Mostly clear", "🌤️"), 2: ("Partly cloudy", "⛅"),
    3: ("Cloudy", "☁️"), 45: ("Fog", "🌫️"), 48: ("Fog", "🌫️"),
    51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Heavy drizzle", "🌦️"),
    61: ("Light rain", "🌧️"), 63: ("Rain", "🌧️"), 65: ("Heavy rain", "🌧️"),
    71: ("Snow", "❄️"), 73: ("Snow", "❄️"), 75: ("Heavy snow", "❄️"),
    80: ("Rain showers", "🌧️"), 81: ("Rain showers", "🌧️"), 82: ("Heavy showers", "🌧️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunderstorm", "⛈️"), 99: ("Thunderstorm", "⛈️"),
}


# ---------- small helper functions ----------
def get_json(url):
    """Download data from the internet and convert it to Python data."""
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def average(values):
    """Average of a list, ignoring empty (None) values."""
    numbers = [v for v in values if v is not None]
    return sum(numbers) / len(numbers) if numbers else None


def most_common(values):
    """The value that appears most often (used for weather codes)."""
    values = [v for v in values if v is not None]
    return Counter(values).most_common(1)[0][0] if values else None


def fmt(value, suffix="", digits=0):
    """Number -> text.  None -> '--'."""
    return "--" if value is None else f"{value:.{digits}f}{suffix}"


def make_label(parent, size, color=TEXT, bold=False, bg=CARD, emoji=False, text=""):
    font = ("Segoe UI Emoji" if emoji else "Segoe UI", size, "bold" if bold else "normal")
    return tk.Label(parent, text=text, font=font, fg=color, bg=bg)


# ---------- getting the weather ----------
def get_model_data(lat, lon, model):
    """Ask ONE weather model for current weather + 6 day forecast."""
    params = {
        "latitude": lat, "longitude": lon,
        "current": ",".join(CURRENT_KEYS + ["weather_code"]),
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_sum,sunrise,sunset",
        "timezone": "Asia/Kolkata", "forecast_days": 6,
    }
    if model:
        params["models"] = model
    try:
        return get_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params))
    except Exception:
        return None


def build_weather(place):
    """Ask all models, then combine their answers into one result."""
    results = {}
    for name, model in MODELS.items():
        data = get_model_data(place["lat"], place["lon"], model)
        if data and data.get("current") and data["current"].get("temperature_2m") is not None:
            results[name] = data

    if not results:                                   # safety net: let the service choose
        data = get_model_data(place["lat"], place["lon"], None)
        if data and data.get("current"):
            results["Auto"] = data
    if not results:
        return None

    runs = list(results.values())

    # current weather = average of all models
    now = {key: average([r["current"].get(key) for r in runs]) for key in CURRENT_KEYS}
    now["weather_code"] = most_common([r["current"].get("weather_code") for r in runs])

    # 5 day forecast = average of all models (index 0 is today, so start at 1)
    days = []
    for i in range(1, 6):
        d = [r["daily"] for r in runs]
        days.append({
            "date": d[0]["time"][i],
            "code": most_common([x["weather_code"][i] for x in d]),
            "max": average([x["temperature_2m_max"][i] for x in d]),
            "min": average([x["temperature_2m_min"][i] for x in d]),
            "rain": average([x["precipitation_sum"][i] for x in d]),
        })

    return {
        "now": now,
        "days": days,
        "model_temps": {name: r["current"]["temperature_2m"] for name, r in results.items()},
        "elevation": runs[0].get("elevation"),
        "sunrise": runs[0]["daily"]["sunrise"][0],
        "sunset": runs[0]["daily"]["sunset"][0],
    }


# ---------- the app window ----------
class WeatherApp:
    def __init__(self, root):
        self.root = root
        root.title("India Live Weather")
        root.geometry("800x740")
        root.configure(bg=BG)

        self.places = []      # search results
        self.place = None     # place being shown

        self.build_screen()
        self.start_search("Mumbai")
        self.auto_refresh()

    def build_screen(self):
        # search bar
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=20, pady=(15, 4))
        self.entry = tk.Entry(top, font=("Segoe UI", 13), bg=CARD, fg=TEXT,
                              insertbackground=TEXT, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.entry.insert(0, "Mumbai")
        self.entry.bind("<Return>", lambda event: self.on_search())
        tk.Button(top, text="🔍 Search", command=self.on_search, bg=ACCENT, fg=BG,
                  font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2",
                  padx=14, pady=6).pack(side="left", padx=(8, 0))

        make_label(self.root, 9, MUTED, bg=BG,
                   text="Examples:   Sonake, Satara     Pushkar, Rajasthan     18.52, 73.85 (latitude, longitude)"
                   ).pack(anchor="w", padx=20)

        # search results (pick the right village from here)
        self.listbox = tk.Listbox(self.root, height=3, bg=CARD, fg=TEXT, relief="flat",
                                  font=("Segoe UI", 11), selectbackground=ACCENT,
                                  selectforeground=BG, highlightthickness=0,
                                  activestyle="none", exportselection=False)
        self.listbox.pack(fill="x", padx=20, pady=6)
        self.listbox.bind("<<ListboxSelect>>", self.on_pick)

        # weather card
        card = tk.Frame(self.root, bg=CARD)
        card.pack(fill="x", padx=20, pady=4)
        self.name = make_label(card, 22, bold=True)
        self.name.pack(pady=(10, 0))
        self.area = make_label(card, 11, ACCENT)
        self.area.pack()

        where_row = tk.Frame(card, bg=CARD)
        where_row.pack(pady=2)
        self.where = make_label(where_row, 10, MUTED, emoji=True)
        self.where.pack(side="left")
        tk.Button(where_row, text="🗺️ Verify on map", command=self.open_map, bg=BG, fg=TEXT,
                  font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
                  padx=8).pack(side="left", padx=10)

        middle = tk.Frame(card, bg=CARD)
        middle.pack(pady=4)
        self.icon = make_label(middle, 48, emoji=True)
        self.icon.pack(side="left", padx=(0, 20))
        self.temp = make_label(middle, 44, ACCENT, bold=True, text="--")
        self.temp.pack(side="left")
        self.desc = make_label(card, 14)
        self.desc.pack()

        # detail boxes
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=15, pady=8)
        self.values = {}
        for i, title in enumerate(["Feels like", "Humidity", "Wind", "Pressure", "Rain now"]):
            row.columnconfigure(i, weight=1, uniform="a")
            box = tk.Frame(row, bg=BG)
            box.grid(row=0, column=i, padx=4, sticky="nsew")
            make_label(box, 9, MUTED, bg=BG, text=title).pack(pady=(6, 0))
            self.values[title] = make_label(box, 13, bold=True, bg=BG, text="--")
            self.values[title].pack(pady=(0, 6))

        self.sun = make_label(card, 10, MUTED, emoji=True)
        self.sun.pack()
        self.models = make_label(card, 10, TEXT)
        self.models.pack(pady=(4, 0))
        self.confidence = make_label(card, 10, GREEN, emoji=True)
        self.confidence.pack(pady=(0, 10))

        # forecast
        make_label(self.root, 13, bold=True, bg=BG, text="5-Day Forecast (average of models)"
                   ).pack(anchor="w", padx=22, pady=(8, 3))
        self.forecast = tk.Frame(self.root, bg=BG)
        self.forecast.pack(fill="x", padx=15)

        # status line
        self.status = make_label(self.root, 10, MUTED, bg=BG)
        self.status.pack(side="bottom", pady=8)

    def set_status(self, text, color=MUTED):
        self.status.config(text=text, fg=color)

    def open_map(self):
        """Open Google Maps at the exact spot, so you can check it is the right village."""
        if self.place:
            webbrowser.open(f"https://www.google.com/maps?q={self.place['lat']},{self.place['lon']}")

    # ---------------- searching ----------------
    def on_search(self):
        self.start_search(self.entry.get().strip())

    def start_search(self, text):
        if not text:
            return
        parts = [p.strip() for p in text.split(",")]

        # if the user typed  latitude, longitude
        try:
            lat, lon = float(parts[0]), float(parts[1])
            self.show_places([{"name": f"{lat}, {lon}", "lat": lat, "lon": lon,
                               "parts": ["Custom location"]}])
            return
        except (ValueError, IndexError):
            pass

        # otherwise search by name  (words after the comma = taluka / district / state)
        self.set_status(f"Searching for {parts[0]}...")
        filters = [p.lower() for p in parts[1:] if p]
        threading.Thread(target=self.find_places, args=(parts[0], filters), daemon=True).start()

    def find_places(self, name, filters):
        url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
            {"name": name, "count": 100, "language": "en", "countryCode": "IN"})
        try:
            results = get_json(url).get("results", [])
        except Exception:
            self.root.after(0, lambda: self.set_status("No internet connection.", RED))
            return

        places = []
        for r in results:
            parts = []      # taluka, district, state
            for key in ("admin4", "admin3", "admin2", "admin1"):
                value = r.get(key)
                if value and value != r["name"] and value not in parts:
                    parts.append(value)
            everything = " ".join([r["name"]] + parts).lower()
            if all(word in everything for word in filters):
                places.append({"name": r["name"], "lat": r["latitude"],
                               "lon": r["longitude"], "parts": parts})

        if places:
            self.root.after(0, self.show_places, places)
        else:
            self.root.after(0, lambda: self.set_status(
                f'"{name}" not found. Try a nearby bigger town or type latitude, longitude.', RED))

    def show_places(self, places):
        self.places = places
        self.listbox.delete(0, "end")
        for p in places:
            self.listbox.insert("end", p["name"] + "  —  " + ", ".join(p["parts"]))
        self.listbox.selection_set(0)
        self.place = places[0]
        self.load_weather()

    def on_pick(self, event):
        picked = self.listbox.curselection()
        if picked:
            self.place = self.places[picked[0]]
            self.load_weather()

    # ---------------- live weather ----------------
    def auto_refresh(self):
        """Runs again and again, every REFRESH_MINUTES minutes."""
        if self.place:
            self.load_weather()
        self.root.after(REFRESH_MINUTES * 60 * 1000, self.auto_refresh)

    def load_weather(self):
        self.set_status("Asking 3 weather models...")
        threading.Thread(target=self.fetch_weather, args=(self.place,), daemon=True).start()

    def fetch_weather(self, place):
        weather = build_weather(place)
        if weather:
            self.root.after(0, self.show_weather, place, weather)
        else:
            self.root.after(0, lambda: self.set_status(
                "Could not get weather. Check your internet.", RED))

    def show_weather(self, place, w):
        if place is not self.place:       # user already picked another place
            return
        now = w["now"]
        text, icon = CODES.get(now["weather_code"], ("Unknown", "🌡️"))

        self.name.config(text=place["name"])
        self.area.config(text="📍 " + " › ".join(place["parts"] + ["India"]))
        elevation = f"  ·  Elevation {w['elevation']:.0f} m" if w["elevation"] is not None else ""
        self.where.config(text=f"🧭 {place['lat']:.3f}°N, {place['lon']:.3f}°E{elevation}")
        self.icon.config(text=icon)
        self.temp.config(text=fmt(now["temperature_2m"], "°C"))
        self.desc.config(text=text)

        self.values["Feels like"].config(text=fmt(now["apparent_temperature"], "°C"))
        self.values["Humidity"].config(text=fmt(now["relative_humidity_2m"], "%"))
        self.values["Wind"].config(text=fmt(now["wind_speed_10m"], " km/h"))
        self.values["Pressure"].config(text=fmt(now["surface_pressure"], " hPa"))
        self.values["Rain now"].config(text=fmt(now["precipitation"], " mm", 1))

        rise = datetime.fromisoformat(w["sunrise"]).strftime("%I:%M %p")
        sets = datetime.fromisoformat(w["sunset"]).strftime("%I:%M %p")
        self.sun.config(text=f"🌅 Sunrise {rise}      🌇 Sunset {sets}")

        # how much do the models agree?
        temps = w["model_temps"]
        self.models.config(text=f"Average of {len(temps)} model(s):   " +
                           "   •   ".join(f"{n} {fmt(t, '°')}" for n, t in temps.items()))
        spread = max(temps.values()) - min(temps.values())
        if len(temps) == 1:
            self.confidence.config(text="🟡 Only 1 model answered - treat as approximate", fg=YELLOW)
        elif spread <= 2:
            self.confidence.config(text="✅ Models agree - high confidence", fg=GREEN)
        elif spread <= 4:
            self.confidence.config(text="🟡 Small difference between models - good confidence", fg=YELLOW)
        else:
            self.confidence.config(text="⚠️ Models disagree - lower confidence, check IMD too", fg=RED)

        # forecast cards
        for widget in self.forecast.winfo_children():
            widget.destroy()
        for i, day in enumerate(w["days"]):
            self.forecast.columnconfigure(i, weight=1, uniform="f")
            name = datetime.strptime(day["date"], "%Y-%m-%d").strftime("%a")
            _, small_icon = CODES.get(day["code"], ("", "🌡️"))

            box = tk.Frame(self.forecast, bg=CARD)
            box.grid(row=0, column=i, padx=5, sticky="nsew")
            make_label(box, 12, bold=True, text=name).pack(pady=(8, 0))
            make_label(box, 24, emoji=True, text=small_icon).pack()
            make_label(box, 13, bold=True, text=fmt(day["max"], "°")).pack()
            make_label(box, 11, MUTED, text=fmt(day["min"], "°")).pack()
            make_label(box, 10, ACCENT, emoji=True,
                       text="💧 " + fmt(day["rain"], " mm", 1)).pack(pady=(0, 8))

        self.set_status(f"● LIVE  •  updated {datetime.now().strftime('%I:%M %p')}  •  "
                        f"auto-refresh every {REFRESH_MINUTES} min", GREEN)


root = tk.Tk()
WeatherApp(root)
root.mainloop()