from datetime import datetime, timezone

CATALOG = {
    "rainfall": {
        "source_class": "PUBLIC/CONFIGURABLE",
        "preferred_source": "IMD operational rainfall/nowcast where authorized",
        "status": "DEMO unless a configured live connector returns fresh data",
        "required_fields": ["timestamp_utc", "lat", "lon", "rainfall_mmhr", "source", "quality_flag"],
    },
    "terrain": {"source_class": "MUNICIPAL/OPEN_GIS", "status": "INGESTION_READY", "required_fields": ["elevation_m", "geometry"]},
    "drainage": {"source_class": "MUNICIPAL", "status": "INGESTION_READY", "required_fields": ["node_id", "pipe_id", "capacity", "geometry"]},
    "observations": {"source_class": "MUNICIPAL/SENSOR/VERIFIED_REPORT", "status": "CALIBRATION_READY", "required_fields": ["timestamp_utc", "location", "water_level_cm", "quality_flag"]},
}

def source_status(source="DEMO_SIMULATION"):
    return {"source": source, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "fresh": source != "DEMO_SIMULATION"}
