from src.graph.mem0_client import get_memory

m = get_memory()
print("Mem0 initialized. Storing memory...")

m.add([{"role": "user", "content": "I love hiking in Yosemite"}], user_id="test")
print("Stored!")

print("Searching...")
r = m.search("outdoor activities", filters={"user_id": "test"}, top_k=3)
for x in r["results"]:
    print("-", x["memory"])
