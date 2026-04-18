import requests

query = """
[out:json];
node["amenity"="school"](around:5000,44.9778,-93.2650);
out;
"""

response = requests.post(
    "https://overpass-api.de/api/interpreter",
    data=query
)

print(response.json())