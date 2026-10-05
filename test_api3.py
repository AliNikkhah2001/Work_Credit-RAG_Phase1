import requests, json
url = "http://127.0.0.1:8000/search/api"
data = {"query": "سلام خسته نباشید رتبه شوهرم Eهست چطور میتونیم درستش کنیم نه اقساطی داریم نه وامی گرفتیم چطور میتونیم درستش کنیم"}
resp = requests.post(url, json=data).json()
for r in resp.get("final_results", []):
    print(r["chunk_id"], r["bm25_score"], r["dense_score"], r["hybrid_score"])
print("Semantic Results Length:", len(resp.get("semantic_results", [])))
