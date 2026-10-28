import requests

url = "http://127.0.0.1:8000/search/api"
data = {"query": "سلام خسته نباشید رتبه شوهرم Eهست چطور میتونیم درستش کنیم نه اقساطی داریم نه وامی گرفتیم چطور میتونیم درستش کنیم"}
resp = requests.post(url, json=data).json()

for i, r in enumerate(resp.get("final_results", [])):
    print(f"Rank {i+1}: {r['chunk_id']} | BM25: {r['bm25_score']} | Dense: {r['dense_score']} | RRF: {r['hybrid_score']}")
