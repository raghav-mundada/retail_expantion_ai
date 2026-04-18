import requests, zipfile, io, geopandas as gpd
from shapely.geometry import Point

# --- Step 1: Download MnDOT AADT shapefile (one time) ---
SHAPEFILE_URL = "https://resources.gisdata.mn.gov/pub/gdrs/data/pub/us_mn_state_dot/trans_aadt_traffic_count_locs/shp_trans_aadt_traffic_count_locs.zip"

print("Downloading MnDOT AADT data...")
r = requests.get(SHAPEFILE_URL)
z = zipfile.ZipFile(io.BytesIO(r.content))
z.extractall("aadt_data/")

# --- Step 2: Load into geopandas ---
gdf = gpd.read_file("aadt_data/")
gdf = gdf.to_crs(epsg=4326)

# --- Step 3: Given a pin, find nearest AADT points within radius ---
lat, lon = 44.9778, -93.2650
radius_meters = 5000

pin = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
pin = pin.to_crs(epsg=3857)
gdf_proj = gdf.to_crs(epsg=3857)

gdf_proj["distance_m"] = gdf_proj.geometry.distance(pin.geometry[0])
nearby = gdf_proj[gdf_proj["distance_m"] <= radius_meters].copy()
nearby = nearby.sort_values("distance_m")

print(f"Found {len(nearby)} AADT count points within {radius_meters}m")
print(nearby[["CURRENT_VO", "ROUTE_LABE", "STREET_NAM", "distance_m"]].head(10))

# --- Step 4: Key features ---
max_aadt = nearby["CURRENT_VO"].max()
avg_aadt = nearby["CURRENT_VO"].mean()
nearest_aadt = nearby.iloc[0]["CURRENT_VO"]
nearest_road = nearby.iloc[0]["STREET_NAM"]

print(f"\nNearest road: {nearest_road}")
print(f"Nearest road AADT: {nearest_aadt:,} vehicles/day")
print(f"Max AADT nearby: {max_aadt:,} vehicles/day")
print(f"Avg AADT nearby: {avg_aadt:,.0f} vehicles/day")