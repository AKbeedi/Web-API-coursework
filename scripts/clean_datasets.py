import pandas as pd

# load raw dataset
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "GlobalWeatherRepository.csv"

df = pd.read_csv(DATA_PATH)

# rename columns to match your schema
df = df.rename(columns={
    "location_name": "city",
    "latitude": "lat",
    "longitude": "lon",
    "temperature_celsius": "temp_c",
    "air_quality_PM2.5": "pm25",
    "last_updated": "obs_date"
})

# convert datetime -> date
df["obs_date"] = pd.to_datetime(df["obs_date"], dayfirst=True).dt.date

# keep only the columns your API needs
df = df[[
    "city",
    "country",
    "lat",
    "lon",
    "obs_date",
    "temp_c",
    "pm25"
]]

# keep latest record per city per day
df = df.sort_values("obs_date").drop_duplicates(
    subset=["city", "country", "obs_date"],
    keep="last"
)

# save cleaned dataset
df.to_csv(BASE_DIR / "data" / "clean_weather.csv", index=False)

print("Dataset cleaned and saved to data/clean_weather.csv")