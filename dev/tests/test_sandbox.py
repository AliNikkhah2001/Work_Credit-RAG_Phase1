import requests
import json

data = {
    "query": "چگونه میتوانم وام بگیرم؟",
    "top_k": 5
}
resp = requests.post("http://127.0.0.1:8000/search/api", json=data)
print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
