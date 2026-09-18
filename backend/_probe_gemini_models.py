import os
import time
from pathlib import Path

for line in Path(".env").read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from google import genai

key = os.environ.get("GEMINI_API_KEY") or ""
print("key_len", len(key))
client = genai.Client(api_key=key)

try:
    names = []
    for m in client.models.list():
        name = getattr(m, "name", None) or str(m)
        low = name.lower()
        if "flash" in low or "lite" in low:
            names.append(name.replace("models/", ""))
    print("AVAILABLE_FLASH_LITE", names[:50])
except Exception as e:
    print("LIST_FAIL", type(e).__name__, str(e)[:220])

candidates = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]
prompt = "Reply with one word: OK. Meeting room for 12 people tomorrow 10am."
for model in candidates:
    t0 = time.time()
    try:
        r = client.models.generate_content(model=model, contents=prompt)
        text = (r.text or "")[:80].replace("\n", " ")
        print(f"OK  {model:28} {time.time() - t0:5.1f}s  {text!r}")
    except Exception as e:
        msg = str(e).replace("\n", " ")[:160]
        print(f"FAIL {model:28} {time.time() - t0:5.1f}s  {msg}")
    time.sleep(1.2)
