from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

response = client.post("/api/runs/batch-delete", json={"run_ids": [1]})
print(f"POST status: {response.status_code}")
print(f"POST response: {response.json()}")

response = client.get("/api/runs/tickers")
print(f"GET status: {response.status_code}")
