import csv
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from app.database import SessionLocal, engine, Base
from app import models

Base.metadata.create_all(bind=engine)

"""
Expected CSV headers:
city,country,lat,lon,obs_date,temp_c,pm25

Example row:
London,United Kingdom,51.52,-0.11,2024-05-16,14.0,16.9
"""

def parse_float(s: str):
    s = (s or "").strip()
    if s == "":
        return None
    return float(s)

def main():
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "  python scripts/import_observations_csv.py <csv_path>\n\n"
            "Example:\n"
            "  python scripts/import_observations_csv.py data/clean_weather.csv\n"
        )
        sys.exit(1)

    csv_path = Path(sys.argv[1])

    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    db = SessionLocal()

    inserted = 0
    skipped = 0
    created_cities = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"city", "country", "lat", "lon", "obs_date", "temp_c", "pm25"}

        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"CSV must contain headers: {sorted(required)}")

        for row in reader:
            city_name = row["city"].strip()
            country = row["country"].strip()
            lat = float(row["lat"])
            lon = float(row["lon"])
            d = datetime.strptime(row["obs_date"].strip(), "%Y-%m-%d").date()
            temp_c = parse_float(row.get("temp_c", ""))
            pm25 = parse_float(row.get("pm25", ""))

            city = (
                db.query(models.City)
                .filter(models.City.name == city_name)
                .filter(models.City.country == country)
                .one_or_none()
            )

            if city is None:
                city = models.City(
                    name=city_name,
                    country=country,
                    lat=lat,
                    lon=lon
                )
                db.add(city)
                db.commit()
                db.refresh(city)
                created_cities += 1
                print(f"Created city: {city.id} {city.name}, {city.country}")

            obs = models.Observation(
                city_id=city.id,
                obs_date=d,
                temp_c=temp_c,
                pm25=pm25
            )

            db.add(obs)
            try:
                db.commit()
                inserted += 1
            except Exception:
                db.rollback()
                skipped += 1

    db.close()
    print(
        f"Done. Created cities: {created_cities}, "
        f"Inserted observations: {inserted}, "
        f"Skipped (duplicates/errors): {skipped}"
    )

if __name__ == "__main__":
    main()