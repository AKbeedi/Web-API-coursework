API Documentation : https://github.com/AKbeedi/Web-API-coursework/blob/ec933a4c84d220a63d96e21888d5d6d5a4d95fc1/api%20documentation.pdf

# Climate & Urban Environment Statistics API

A **FastAPI-based backend system** for storing and analysing historical urban climate data.

The API stores environmental observations (temperature and PM2.5) for cities and provides statistical analysis endpoints including **trend analysis, anomaly detection, environmental risk scoring, regime classification, and city comparisons**.

This project was developed as part of a university coursework assignment on **API development and statistical data analysis**.

---

# Features

- CRUD operations for city records
- Historical observation storage (temperature and PM2.5)
- Summary statistics for selected date ranges
- Trend analysis with moving averages
- Statistical anomaly detection
- Environmental risk scoring
- Environmental regime classification
- City comparison analytics
- City environmental rankings
- Interactive frontend dashboard
- Automated testing with pytest
- Smoke testing script for API validation

---

# Live API

Deployed API:

```
https://web-api-coursework.onrender.com
```

Interactive API documentation:

```
https://web-api-coursework.onrender.com/docs
```

---

# Setup

## 1. Create a virtual environment

```bash
python -m venv .venv
```

Activate it.

**Windows**

```bash
.venv\Scripts\activate
```

**Mac/Linux**

```bash
source .venv/bin/activate
```

---

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

---

# Running the API

Start the FastAPI server: (2 ways) FROM the root folder

```bash
uvicorn app.main:app --reload
python -m uvicorn app.main:app --reload
```

Open the API documentation:

```
http://127.0.0.1:8000/docs
```

---

# Dataset

The API uses historical environmental observations containing **temperature and PM2.5 measurements for multiple cities**.

Observation data was imported into the database during development using a custom Python import script.

https://www.kaggle.com/datasets/nelgiriyewithana/global-weather-repository


## Importing the Dataset

Before running the analytics endpoints, the dataset must be imported into the database.

Run the import script from the **project root directory**:

```bash
python scripts/import_observations_csv.py data/clean_weather.csv
```

This script will:

- create city records if they do not already exist
- insert environmental observations for each city
- skip duplicate observations automatically

Once the dataset has been imported, the API endpoints and dashboard will return populated results.




---

# Example Endpoints

## Cities

```
GET /cities
GET /cities/{city_id}
POST /cities
PUT /cities/{city_id}
DELETE /cities/{city_id}
```

## Observations

```
GET /observations?city_id={id}
```

## Analytics

```
GET /cities/{id}/summary
GET /cities/{id}/trend
GET /cities/{id}/anomalies
GET /cities/{id}/risk-score
GET /cities/{id}/regimes
GET /cities/{id}/insights
GET /cities/compare
GET /cities/rankings
```

---

# Dashboard

The project includes a simple **frontend dashboard** that visualises API results.

Open in a browser:

```
http://127.0.0.1:8000/dashboard
```

The dashboard allows users to:

- visualise climate trends
- highlight statistical anomalies
- view environmental risk scores
- compare cities

---

# Testing

The project includes **automated API tests using pytest**.

Run all tests with: (FROM THE ROOT FOLDER)

```bash
pytest
python -m pytest
```

The test suite covers:

- city CRUD operations
- summary statistics
- anomaly detection
- trend analysis
- environmental risk scoring
- regime classification
- city comparison
- rankings

A smoke testing script is also included to validate the deployed API.

Run:

```bash
python scripts/smoke_test_api.py
```

---

# API Documentation

Full API documentation is available via the **FastAPI interactive documentation interface**:

```
/docs
```

This documentation includes:

- endpoint descriptions
- request parameters
- response schemas
- example responses

A full exported API documentation PDF is also included with the coursework submission.

---

# Project Structure

```
app/
    main.py
    models.py
    schemas.py
    database.py

scripts/
    import_observations_csv.py
    smoke_test_api.py

tests/
    conftest.py
    test_city_crud.py
    test_summary.py
    test_anomalies.py
    test_analytics_extra.py

data/

app/static/
    dashboard.html

requirements.txt
README.md
```

---

# Technologies Used

- **FastAPI** – API framework  
- **SQLAlchemy** – ORM and database models  
- **SQLite / SQL database** – data storage  
- **Pydantic** – request/response validation  
- **pytest** – automated testing  
- **Uvicorn** – ASGI server  

---

# Licence

This project was developed for **educational purposes as part of university coursework**.
