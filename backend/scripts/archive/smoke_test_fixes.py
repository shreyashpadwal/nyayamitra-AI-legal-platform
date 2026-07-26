"""Minimal direct smoke test — no health-check loop, no fancy output."""
import sys, io, json, time, urllib.request, urllib.error, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000/api"

# 1. Register throwaway user (ignore 400/409 if already exists)
reg = json.dumps({"username":"smoketest_fix","email":"smoketest_fix@nyaya.local",
                  "password":"Smoke_test_99","role":"citizen"}).encode()
try:
    with urllib.request.urlopen(
        urllib.request.Request(f"{BASE}/auth/register", data=reg,
                               headers={"Content-Type":"application/json"}), timeout=10) as r:
        print("Registered OK")
except urllib.error.HTTPError as e:
    print(f"Register: {e.code} (probably already exists, continuing)")

# 2. Login
login = json.dumps({"email":"smoketest_fix@nyaya.local","password":"Smoke_test_99"}).encode()
with urllib.request.urlopen(
    urllib.request.Request(f"{BASE}/auth/login", data=login,
                           headers={"Content-Type":"application/json"}), timeout=10) as r:
    token = json.loads(r.read())["access_token"]
print("Login OK")

# 3. Ask IPC theft question
ask = json.dumps({"question":"What is the punishment for theft under IPC Section 379 and 380?"}).encode()
print("Sending query... (may take 30-60s)")
t0 = time.time()
with urllib.request.urlopen(
    urllib.request.Request(f"{BASE}/citizen/ask", data=ask,
                           headers={"Content-Type":"application/json",
                                    "Authorization":f"Bearer {token}"}), timeout=120) as r:
    result = json.loads(r.read())
elapsed = round(time.time()-t0, 2)

print(f"\nCompleted in {elapsed}s | method={result.get('retrieval_method')} | hallucination={result.get('hallucination_status')}")

# 4. Source card check
print("\n=== SOURCE CARDS ===")
sources = result.get("sources", [])
for s in sources:
    wrong = " *** WRONG LAW ***" if "crpc" in str(s.get("law","")).lower() else ""
    print(f"  chunk={s['chunk_index']}  law={s['law']!r}  page={s['page']}{wrong}")

laws = {s.get("law","") for s in sources}
if not sources:
    print("  (no sources)")
elif all("Indian Penal Code" in l or "Web" in l for l in laws):
    print("\nFix 1 PASS -- all sources are Indian Penal Code")
else:
    print(f"\nFix 1 FAIL -- unexpected laws: {laws}")

# 5. Page-number consistency check
answer = result.get("answer","")
cited = re.findall(r"pg\s*(\d+)", answer, re.IGNORECASE)
card_pages = [str(s.get("page","")) for s in sources]
print(f"\nInline cited pages : {cited}")
print(f"Source card pages  : {card_pages}")
overlap = set(cited) & set(card_pages)
if cited and card_pages:
    print(f"Fix 2 {'PASS' if overlap else 'CHECK (no exact match - see answer below)'}  overlap={overlap}")

print("\n=== ANSWER (first 600 chars) ===")
print(answer[:600])
