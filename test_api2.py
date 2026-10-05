import requests
url = "http://127.0.0.1:8000/search/api"
data = {"query": "سلام خسته نباشید رتبه شوهرم1234 Eهست چطور میتونیم درستش کنیم نه اقساطی داریم نه وامی گرفتیم چطور میتونیم درستش کنیم"}
resp = requests.post(url, json=data).json()
for r in resp.get("semantic_results", [])[:5]:
    print("Semantic chunk:", r["chunk_id"], r["semantic_score"])
print("Total semantic results:", len(resp.get("semantic_results", [])))
