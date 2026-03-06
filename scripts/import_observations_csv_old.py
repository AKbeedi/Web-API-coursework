import csv
import sys
from datetime import datetime

sys.path.append(".")

from app.database import SessionLocal, engine, Base
from app import models

Base.metadata.create_all(bind=engine)

"""
Expected CSV headers:
date,temp_c,pm25

Example row:
2025-01-01,5.2,12.8
"""

def parse_float(s: str):
    s = (s or "").strip()
    if s == "":
        return None
    return float(s)

def main():
    if len(sys.argv) < 7:
        print(
            "Usage:\n"
            "  python scripts/import_observations_csv.py <csv_path> <city_name> <country> <lat> <lon> <date_format>\n\n"
            "Example:\n"
            "  python scripts/import_observations_csv.py data/sample_observations.csv Leeds UK 53.8008 -1.5491 %Y-%m-%d\n"
        )
        sys.exit(1)

    csv_path = sys.argv[1]
    city_name = sys.argv[2]
    country = sys.argv[3]
    lat = float(sys.argv[4])
    lon = float(sys.argv[5])
    date_format = sys.argv[6]

    db = SessionLocal()

    city = (
        db.query(models.City)
        .filter(models.City.name == city_name)
        .filter(models.City.country == country)
        .one_or_none()
    )
    if city is None:
        city = models.City(name=city_name, country=country, lat=lat, lon=lon)
        db.add(city)
        db.commit()
        db.refresh(city)
        print(f"Created city: {city.id} {city.name}, {city.country}")
    else:
        print(f"Using existing city: {city.id} {city.name}, {city.country}")

    inserted = 0
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"date", "temp_c", "pm25"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"CSV must contain headers: {sorted(required)}")

        for row in reader:
            d = datetime.strptime(row["date"].strip(), date_format).date()
            temp_c = parse_float(row.get("temp_c", ""))
            pm25 = parse_float(row.get("pm25", ""))

            obs = models.Observation(
            city_id=city.id,
            obs_date=d,     # renamed
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
    print(f"Done. Inserted: {inserted}, Skipped (duplicates/errors): {skipped}")

if __name__ == "__main__":
    main()
