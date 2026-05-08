import httpx
import asyncio

async def trigger():
    url = "http://127.0.0.1:6767/api/analysis/batch"
    payload = {
        "tickers": ["AAPL"],
        "dates": ["2026-05-08"],
        "force": False,
        "skip_completed": True
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10.0)
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(trigger())
