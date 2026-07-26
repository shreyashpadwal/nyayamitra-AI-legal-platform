"""
Quick curl-style test of the /citizen/ask-stream SSE endpoint.
Logs in, then sends a streaming request and prints each SSE event as it arrives.
Usage: cd backend && python -m scripts.test_sse_endpoint
"""
import sys, io, json, time, requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE = "http://127.0.0.1:8000/api"

# --- Login ---
try:
    requests.post(f"{BASE}/auth/register", json={"username": "sse_tester", "email": "sse_tester@nyaya.local", "password": "test1234", "role": "citizen"})
except Exception:
    pass
login = requests.post(f"{BASE}/auth/login", json={"email": "sse_tester@nyaya.local", "password": "test1234"})
assert login.ok, f"Login failed: {login.text}"
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

QUERY = "What is the punishment for theft in IPC?"
print(f"Sending streaming query: {QUERY!r}")
print("-" * 60)

t0 = time.time()
with requests.post(
    f"{BASE}/citizen/ask-stream",
    json={"question": QUERY},
    headers=headers,
    stream=True,
    timeout=120,
) as r:
    assert r.ok, f"Endpoint error {r.status_code}: {r.text[:200]}"
    buffer = ""
    for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
        buffer += chunk
        parts = buffer.split("\n\n")
        buffer = parts.pop()
        for part in parts:
            line = part.strip()
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            elapsed = round(time.time() - t0, 2)
            if event["type"] == "status":
                print(f"  [{elapsed:5.1f}s] STATUS  : {event['message']}")
            elif event["type"] == "final":
                print(f"  [{elapsed:5.1f}s] FINAL   : answer={event['answer'][:80]!r}...")
                print(f"            sources: {len(event.get('sources', []))} items")
            elif event["type"] == "error":
                print(f"  [{elapsed:5.1f}s] ERROR   : {event['message']}")

print(f"\nTotal: {round(time.time()-t0, 2)}s")
print("SSE endpoint OK ✅")
