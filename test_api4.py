import requests, json
url = "http://127.0.0.1:8000/search/api"
data = {"query": "سلام خسته نباشید رتبه شوهرم Eهست چطور میتونیم درستش کنیم نه اقساطی داریم نه وامی گرفتیم چطور میتونیم درستش کنیم", "filter_path": "اشخاص حقوقی"}
resp = requests.post(url, json=data).json()
print("Final Results Length:", len(resp.get("final_results", [])))
if len(resp.get("final_results", [])) > 0:
    print(resp.get("final_results")[0]["heading_path"])
