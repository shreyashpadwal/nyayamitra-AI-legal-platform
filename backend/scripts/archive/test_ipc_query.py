"""Quick smoke-test for the two citation fixes."""
import sys, io, time, json, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000/api"

# Login
login_payload = json.dumps({"email": "test_py@example.com", "password": "test123"}).encode()
req = urllib.request.Request(
    f"{BASE}/auth/login",
    data=login_payload,
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=15) as r:
    token = json.loads(r.read())["access_token"]
print("Login OK")

# Ask the IPC theft question
ask_payload = json.dumps(
    {"question": "What is the punishment for theft under IPC Section 379 and 380?"}
).encode()
req2 = urllib.request.Request(
    f"{BASE}/citizen/ask",
    data=ask_payload,
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    },
)
print("Sending query ...")
t0 = time.time()
with urllib.request.urlopen(req2, timeout=90) as r:
    result = json.loads(r.read())
elapsed = round(time.time() - t0, 2)

print(f"\nDone in {elapsed}s | retrieval={result.get('retrieval_method')} | hallucination={result.get('hallucination_status')}")

print("\n=== SOURCE CARDS ===")
for s in result.get("sources", []):
    print(f"  chunk={s['chunk_index']}  law={s['law']}  page={s['page']}")

print("\n=== ANSWER (first 600 chars) ===")
print(result.get("answer", "")[:600])
