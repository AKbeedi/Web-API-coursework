# Climate & Urban Environment Statistics API

A FastAPI-based backend system for storing and analysing historical urban climate data.

The API stores environmental observations (temperature and PM2.5) for cities and provides statistical analysis endpoints including trends, anomaly detection, environmental risk scoring, and city comparisons.

This project was developed as part of a university coursework assignment on API development and data analysis.

---

## Features

- CRUD operations for city records
- Historical observation storage (temperature and PM2.5)
- Summary statistics for selected date ranges
- Trend analysis with moving averages
- Statistical anomaly detection
- Environmental risk scoring
- Environmental regime classification
- City comparison analytics
- Interactive frontend dashboard
- Automated smoke testing script

---

## Live API

Deployed API:

https://YOUR-API.onrender.com

Interactive API documentation:

https://YOUR-API.onrender.com/docs

---

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
```

Activate it.

Windows:

```bash
.venv\Scripts\activate
```

Mac/Linux:

```bash
source .venv/bin/activate
```

---

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the API

```bash
uvicorn app.main:app --reload
```

Visit:

```
http://127.0.0.1:8000/docs
```

---

## Dataset

The API uses historical environmental observations containing temperature and PM2.5 measurements for multiple cities.

Observation data was imported into the database during development using a custom Python import script.

---

## Example Endpoints

### Cities

```
GET /cities
GET /cities/{city_id}
POST /cities
```

### Observations

```
GET /observations?city_id={id}
```

### Analytics

```
GET /cities/{id}/summary
GET /cities/{id}/trend
GET /cities/{id}/anomalies
GET /cities/{id}/risk-score
GET /cities/{id}/regimes
GET /cities/compare
```

---

## Dashboard

The project includes a simple frontend dashboard that visualises API results.

Open:

```
dashboard.html
```

The dashboard allows users to:

- visualise climate trends
- highlight anomalies
- view environmental risk scores
- compare cities

---

## Testing

A smoke testing script is included to validate API endpoints.

Run:

```bash
python scripts/smoke_test_api.py
```

---

## API Documentation

Full API documentation is available via the FastAPI interactive documentation:

```
/docs
```

This documentation includes request parameters, response schemas, and example responses.

---

## Project Structure

```
app/
    main.py
    models.py
    schemas.py
    database.py

scripts/
    import_observations_csv.py
    smoke_test_api.py

data/

dashboard.html
requirements.txt
README.md
```