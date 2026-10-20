import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from providers.omniroute_provider import OmniRouteProvider

p = OmniRouteProvider()
m = p.select_active_model()
print("Active model:", m)
res = p.chat_completion(
    [
        {"role": "system", "content": "You are a JSON assistant. Output valid JSON only."},
        {"role": "user", "content": 'Return a JSON object with key "audit" and value "passed".'},
    ],
    model=m,
)
print("Result success:", res.get("success"))
print("Result content:", res.get("content"))
print("Result error:", res.get("error"))
