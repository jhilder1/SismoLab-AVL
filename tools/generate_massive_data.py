import json
import random
from datetime import datetime, timedelta

def generate_massive():
    ZONES = [
        {"name": "Norte", "x_min": 0, "x_max": 500, "y_min": 500, "y_max": 1000, "is_populated": True},
        {"name": "Centro", "x_min": 200, "x_max": 800, "y_min": 200, "y_max": 800, "is_populated": True},
        {"name": "Sur", "x_min": 0, "x_max": 500, "y_min": 0, "y_max": 500, "is_populated": False},
        {"name": "Costa", "x_min": 500, "x_max": 1000, "y_min": 0, "y_max": 500, "is_populated": True},
    ]
    STATIONS = [
        {"station_id": "EST-001", "name": "Estacion Norte"},
        {"station_id": "EST-002", "name": "Estacion Centro"},
        {"station_id": "EST-003", "name": "Estacion Sur"},
        {"station_id": "EST-004", "name": "Estacion Costa"},
    ]
    
    events = []
    base_time = datetime(2026, 6, 1)
    
    for i in range(1, 1501):
        mag = round(random.uniform(2.5, 8.5), 1)
        depth = round(random.uniform(5.0, 150.0), 1)
        x = round(random.uniform(0.0, 1000.0), 1)
        y = round(random.uniform(0.0, 1000.0), 1)
        st = random.choice(STATIONS)["station_id"]
        
        # Add random minutes
        t = base_time + timedelta(minutes=random.randint(0, 43200)) 
        
        events.append({
            "event_id": 10000 + i,
            "magnitude": mag,
            "depth_km": depth,
            "epicenter": {"x": x, "y": y},
            "occurrence_time": t.isoformat() + "Z",
            "station_id": st
        })
        
    data = {
        "format": "sismolab-insertions",
        "description": "1500 eventos generados aleatoriamente para pruebas de carga",
        "clock": "2026-07-01T23:59:00Z",
        "zones": ZONES,
        "stations": STATIONS,
        # No "parameters": the load keeps the W, R, L and T set before it (Section 9).
        "events": events,
    }
    
    with open('data/insertions/prueba_carga_masiva_1500.json', 'w') as f:
        json.dump(data, f, indent=2)
        
if __name__ == '__main__':
    generate_massive()
