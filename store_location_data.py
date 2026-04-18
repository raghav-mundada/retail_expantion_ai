import requests
import json

query = """
[out:json][timeout:25];
node["shop"="supermarket"](around:5000, 44.9778, -93.2650);
out body;
"""

r = requests.get(
    "https://overpass-api.de/api/interpreter",
    params={"data": query},
    timeout=30
)

print("Status:", r.status_code)
print("Response length:", len(r.text))

if r.status_code != 200:
    print("Error response:", r.text[:500])
else:
    data = r.json()
    nodes = data.get("elements", [])
    print(f"Found {len(nodes)} locations\n")
    for n in nodes:
        tags = n.get("tags", {})
        name = tags.get("name", "Unknown")
        lat = n.get("lat")
        lon = n.get("lon")
        print(f"{name} | {lat}, {lon}")