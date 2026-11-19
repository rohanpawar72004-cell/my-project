"""
India LIVE Weather App (simple version)
- Search any village / town / city in India
- Live weather, refreshes by itself every 10 minutes
- 5 day forecast
- Free data from Open-Meteo (no API key needed)
"""

import json
import threading
import tkinter as tk
import urllib.parse
import urllib.request
from datetime import datetime

# ---------- settings ----------
BG, CARD, TEXT, MUTED, ACCENT = "#0f172a", "#1e293b", "#f1f5f9", "#94a3b8", "#38bdf8"
GREEN, RED = "#4ade80", "#f87171"
REFRESH_MINUTES = 10          # how often the weather updates by itself

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


def get_json(url):
    """Download data from the internet and convert it to Python data."""
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def make_label(parent, size, color=TEXT, bold=False, bg=CARD, emoji=False, text=""):
    """Small helper so we don't repeat the same label code again and again."""
    font = ("Segoe UI Emoji" if emoji else "Segoe UI", size, "bold" if bold else "normal")
    return tk.Label(parent, text=text, font=font, fg=color, bg=bg)


class WeatherApp:
    def __init__(self, root):
        self.root = root
        root.title("India Live Weather")
        root.geometry("780x820")
        root.configure(bg=BG)

        self.places = []      # search results
        self.place = None     # place being shown

        self.build_screen()
        self.start_search("Mumbai")
        self.auto_refresh()

    # ---------------- screen ----------------
    def build_screen(self):
        # search bar
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=20, pady=(20, 5))
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

        # search results list
        self.listbox = tk.Listbox(self.root, height=4, bg=CARD, fg=TEXT, relief="flat",
                                  font=("Segoe UI", 11), selectbackground=ACCENT,
                                  selectforeground=BG, highlightthickness=0,
                                  activestyle="none", exportselection=False)
        self.listbox.pack(fill="x", padx=20, pady=8)
        self.listbox.bind("<<ListboxSelect>>", self.on_pick)

        # big weather card
        card = tk.Frame(self.root, bg=CARD)
        card.pack(fill="x", padx=20, pady=5)
        self.name = make_label(card, 24, bold=True)
        self.name.pack(pady=(15, 0))
        self.area = make_label(card, 11, ACCENT)
        self.area.pack()

        middle = tk.Frame(card, bg=CARD)
        middle.pack(pady=8)
        self.icon = make_label(middle, 60, emoji=True)
        self.icon.pack(side="left", padx=(0, 20))
        self.temp = make_label(middle, 52, ACCENT, bold=True, text="--")
        self.temp.pack(side="left")
        self.desc = make_label(card, 15)
        self.desc.pack()

        # small detail boxes
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=15, pady=10)
        self.values = {}
        for i, title in enumerate(["Feels like", "Humidity", "Wind", "Pressure", "Rain now"]):
            row.columnconfigure(i, weight=1, uniform="a")
            box = tk.Frame(row, bg=BG)
            box.grid(row=0, column=i, padx=4, sticky="nsew")
            make_label(box, 9, MUTED, bg=BG, text=title).pack(pady=(8, 0))
            self.values[title] = make_label(box, 13, bold=True, bg=BG, text="--")
            self.values[title].pack(pady=(0, 8))

        self.sun = make_label(card, 11, MUTED, emoji=True)
        self.sun.pack(pady=(0, 15))

        # forecast
        make_label(self.root, 14, bold=True, bg=BG, text="5-Day Forecast").pack(anchor="w", padx=22, pady=(10, 4))
        self.forecast = tk.Frame(self.root, bg=BG)
        self.forecast.pack(fill="x", padx=15)

        # live status line
        self.status = make_label(self.root, 10, MUTED, bg=BG)
        self.status.pack(side="bottom", pady=10)

    def set_status(self, text, color=MUTED):
        self.status.config(text=text, fg=color)

    # ---------------- searching ----------------
    def on_search(self):
        self.start_search(self.entry.get().strip())

    def start_search(self, text):
        if not text:
            return
        parts = [p.strip() for p in text.split(",")]

        # if user typed  latitude, longitude
        try:
            lat, lon = float(parts[0]), float(parts[1])
            self.show_places([{"name": f"{lat}, {lon}", "lat": lat, "lon": lon,
                               "parts": ["Custom location"]}])
            return
        except (ValueError, IndexError):
            pass

        # otherwise search by name   (words after the comma = district / state)
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
        self.set_status("Updating...")
        threading.Thread(target=self.fetch_weather, args=(self.place,), daemon=True).start()

    def fetch_weather(self, place):
        url = ("https://api.open-meteo.com/v1/forecast?latitude=" + str(place["lat"]) +
               "&longitude=" + str(place["lon"]) +
               "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
               "precipitation,weather_code,wind_speed_10m,surface_pressure"
               "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
               "precipitation_probability_max,sunrise,sunset"
               "&timezone=Asia%2FKolkata&forecast_days=6")
        try:
            data = get_json(url)
            self.root.after(0, self.show_weather, place, data)
        except Exception:
            self.root.after(0, lambda: self.set_status("No internet connection.", RED))

    def show_weather(self, place, data):
        if place is not self.place:       # user already picked another place
            return
        now, daily = data["current"], data["daily"]
        text, icon = CODES.get(now["weather_code"], ("Unknown", "🌡️"))

        self.name.config(text=place["name"])
        self.area.config(text="📍 " + " › ".join(place["parts"] + ["India"]))
        self.icon.config(text=icon)
        self.temp.config(text=f"{round(now['temperature_2m'])}°C")
        self.desc.config(text=text)

        self.values["Feels like"].config(text=f"{round(now['apparent_temperature'])}°C")
        self.values["Humidity"].config(text=f"{now['relative_humidity_2m']}%")
        self.values["Wind"].config(text=f"{round(now['wind_speed_10m'])} km/h")
        self.values["Pressure"].config(text=f"{round(now['surface_pressure'])} hPa")
        self.values["Rain now"].config(text=f"{now['precipitation']} mm")

        rise = datetime.fromisoformat(daily["sunrise"][0]).strftime("%I:%M %p")
        sets = datetime.fromisoformat(daily["sunset"][0]).strftime("%I:%M %p")
        self.sun.config(text=f"🌅 Sunrise {rise}      🌇 Sunset {sets}")

        # 5 day forecast (index 0 is today, so start from 1)
        for widget in self.forecast.winfo_children():
            widget.destroy()
        for i in range(1, 6):
            self.forecast.columnconfigure(i - 1, weight=1, uniform="f")
            day = datetime.strptime(daily["time"][i], "%Y-%m-%d").strftime("%a")
            _, small_icon = CODES.get(daily["weather_code"][i], ("", "🌡️"))
            rain = daily["precipitation_probability_max"][i] or 0

            box = tk.Frame(self.forecast, bg=CARD)
            box.grid(row=0, column=i - 1, padx=5, sticky="nsew")
            make_label(box, 12, bold=True, text=day).pack(pady=(10, 0))
            make_label(box, 26, emoji=True, text=small_icon).pack()
            make_label(box, 13, bold=True, text=f"{round(daily['temperature_2m_max'][i])}°").pack()
            make_label(box, 11, MUTED, text=f"{round(daily['temperature_2m_min'][i])}°").pack()
            make_label(box, 10, ACCENT, emoji=True, text=f"💧 {rain}%").pack(pady=(0, 10))

        self.set_status(f"● LIVE  •  updated {datetime.now().strftime('%I:%M %p')}  •  "
                        f"auto-refresh every {REFRESH_MINUTES} min", GREEN)


root = tk.Tk()
WeatherApp(root)
root.mainloop()