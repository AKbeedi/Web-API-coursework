# Climate & Urban Environment Statistics API

A FastAPI-based backend system for storing and analysing historical urban climate data.

## Features

- Full CRUD operations for Cities
- Historical observation storage (temperature, PM2.5)
- Summary statistics endpoint
- Trend analysis with moving averages
- CSV dataset ingestion script
- Statistical anomaly detection using z-score method


---

## Setup

### 1. Create virtual environment

python -m venv .venv

Activate it:

Windows:
.venv\Scripts\activate

Mac/Linux:
source .venv/bin/activate

### 2. Install dependencies

pip install fastapi uvicorn sqlalchemy pydantic

---

## Running the API

python -m uvicorn app.main:app --reload

Visit:
http://127.0.0.1:8000/docs

---

## Importing Dataset

python scripts/import_observations_csv.py data/sample_observations.csv Leeds UK 53.8008 -1.5491 %Y-%m-%d

---

## Example Endpoints

GET /cities  
POST /cities  
GET /observations?city_id=1  
GET /cities/1/summary  
GET /cities/1/trend
