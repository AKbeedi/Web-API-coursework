import requests

BASE_URL = "http://127.0.0.1:8000"

# Pick a few known IDs from your /cities output
TEST_CITY_IDS = {
    "London": 133,
    "Beijing": 92,
    "Jakarta": 50,
}

def check(name, url, expected_status=200):
    try:
        r = requests.get(url, timeout=10)
        ok = r.status_code == expected_status
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        print(f"  URL: {url}")
        print(f"  Status: {r.status_code}")
        if not ok:
            print(f"  Body: {r.text[:400]}")
        return ok
    except Exception as e:
        print(f"[FAIL] {name}")
        print(f"  URL: {url}")
        print(f"  Error: {e}")
        return False

def main():
    passed = 0
    total = 0

    tests = [
        ("Root", f"{BASE_URL}/"),
        ("List cities", f"{BASE_URL}/cities"),
        ("Missing city returns 404", f"{BASE_URL}/cities/999999", 404),
    ]

    for name, url, *rest in tests:
        total += 1
        expected = rest[0] if rest else 200
        if check(name, url, expected):
            passed += 1

    for city_name, city_id in TEST_CITY_IDS.items():
        city_tests = [
            (f"{city_name} city lookup", f"{BASE_URL}/cities/{city_id}", 200),
            (
                f"{city_name} observations",
                f"{BASE_URL}/observations?city_id={city_id}",
                200,
            ),
            (
                f"{city_name} summary",
                f"{BASE_URL}/cities/{city_id}/summary?start=2024-05-16&end=2024-05-21",
                200,
            ),
            (
                f"{city_name} temp trend",
                f"{BASE_URL}/cities/{city_id}/trend?metric=temp_c&start=2024-05-16&end=2024-05-21",
                200,
            ),
            (
                f"{city_name} pm25 anomalies",
                f"{BASE_URL}/cities/{city_id}/anomalies?metric=pm25&start=2024-05-16&end=2024-05-21",
                200,
            ),
            (
                f"{city_name} risk score",
                f"{BASE_URL}/cities/{city_id}/risk-score?start=2024-05-16&end=2024-05-21",
                200,
            ),
            (
                f"{city_name} regimes",
                f"{BASE_URL}/cities/{city_id}/regimes?metric=pm25&start=2024-05-16&end=2024-05-21",
                200,
            ),
        ]

        for name, url, expected in city_tests:
            total += 1
            if check(name, url, expected):
                passed += 1

    # Invalid-input tests
    invalid_tests = [
        (
            "Invalid trend metric returns 422",
            f"{BASE_URL}/cities/133/trend?metric=wrong&start=2024-05-16&end=2024-05-21",
            422,
        ),
        (
            "Invalid date range returns 422",
            f"{BASE_URL}/cities/133/summary?start=2024-05-21&end=2024-05-16",
            422,
        ),
        (
            "No data range returns 404",
            f"{BASE_URL}/cities/133/summary?start=2020-01-01&end=2020-01-02",
            404,
        ),
    ]

    for name, url, expected in invalid_tests:
        total += 1
        if check(name, url, expected):
            passed += 1

    print("\n---")
    print(f"Passed {passed}/{total} tests")

if __name__ == "__main__":
    main()