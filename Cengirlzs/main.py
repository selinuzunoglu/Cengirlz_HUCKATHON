from fastapi import FastAPI, WebSocket, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import numpy as np
import pandas as pd
import asyncio
from sqlalchemy import create_engine, text
import random
from datetime import datetime
from prophet import Prophet

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ENERGY_TYPES = [
    "Solar", "Wind", "Battery", "Factory", "Hydro", "Geothermal", "Nuclear"
]
sim_params = {
    "Solar":      {"mean": 50, "std": 10},
    "Wind":       {"mean": 40, "std": 8},
    "Battery":    {"mean": 30, "std": 15},
    "Factory":    {"mean": 70, "std": 20},
    "Hydro":      {"mean": 60, "std": 12},
    "Geothermal": {"mean": 35, "std": 7},
    "Nuclear":    {"mean": 90, "std": 10}
}

DATABASE_URL = "postgresql+psycopg2://postgres:ankara123@localhost:5432/cengirlzs"

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        print("PostgreSQL bağlantısı başarılı!")
except Exception as e:
    print("Bağlantı hatası:", e)

storage_levels = {et: 0.0 for et in ENERGY_TYPES}
storage_capacity = 500.0

@app.get("/dashboard")
def get_dashboard():
    return FileResponse("dashboard.html")

@app.get("/")
def root():
    return {"message": "Enerji Akışı İzleme Sistemi API"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    history = []
    global storage_levels
    while True:
        now = pd.Timestamp.now()
        data_point = {"timestamp": now.strftime("%H:%M:%S")}
        for energy_type in ENERGY_TYPES:
            value = float(np.random.normal(sim_params[energy_type]["mean"], sim_params[energy_type]["std"]))
            outgoing = float(np.random.uniform(0, value))  # Bağımsız rastgele giden
            loss = float(np.random.uniform(0, value - outgoing))  # Bağımsız rastgele kayıp (üretimden giden çıktıktan sonra)
            # Depolama = Önceki Depolama + (Üretim - Giden - Kayıp)
            storage = storage_levels[energy_type] + (value - outgoing - loss)
            if storage > storage_capacity:
                storage = storage_capacity
            if storage < 0:
                storage = 0
            storage_levels[energy_type] = storage
            route_name = random.choice(['A', 'B', 'C', 'D'])
            # Veritabanına kaydet
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO energy_data (timestamp, energy_type, value, outgoing, loss, storage, route_name)
                        VALUES (:timestamp, :energy_type, :value, :outgoing, :loss, :storage, :route_name)
                    """),
                    {"timestamp": now, "energy_type": energy_type, "value": value, "outgoing": outgoing, "loss": loss, "storage": storage, "route_name": route_name}
                )
            data_point[energy_type] = {"value": value, "outgoing": outgoing, "loss": loss, "storage": storage, "route_name": route_name}
        history.append(data_point)
        if len(history) > 100:
            history.pop(0)
        await websocket.send_json({
            "timestamp": data_point["timestamp"],
            "data": data_point,
            "history": history[-50:]  # Son 50 zaman dilimi
        })
        await asyncio.sleep(3)

@app.get("/api/history")
def get_history(
    energy_type: str = Query(None),
    route_name: str = Query(None),
    start: str = Query(None),
    end: str = Query(None)
):
    try:
        query = "SELECT timestamp, energy_type, value, outgoing, loss, storage, route_name FROM energy_data WHERE 1=1"
        params = {}
        if energy_type:
            query += " AND energy_type = :energy_type"
            params["energy_type"] = energy_type
        if route_name:
            query += " AND route_name = :route_name"
            params["route_name"] = route_name
        if start:
            query += " AND timestamp >= :start"
            params["start"] = start
        if end:
            query += " AND timestamp <= :end"
            params["end"] = end
        query += " ORDER BY timestamp DESC LIMIT 500"
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            rows = [dict(r._mapping) for r in result]
        return {"data": rows}
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/anomalies")
def add_anomaly(
    timestamp: str = Body(...),
    energy_type: str = Body(...),
    route_name: str = Body(...),
    value: float = Body(...)
):
    print(f"[ANOMALY POST] timestamp={timestamp}, energy_type={energy_type}, route_name={route_name}, value={value}")
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO anomalies (timestamp, energy_type, route_name, value)
                    VALUES (:timestamp, :energy_type, :route_name, :value)
                """),
                {
                    "timestamp": timestamp,
                    "energy_type": energy_type,
                    "route_name": route_name,
                    "value": value
                }
            )
        print("[ANOMALY POST] Success!")
        return {"status": "ok"}
    except Exception as e:
        print(f"[ANOMALY POST] ERROR: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/anomalies")
def get_anomalies(
    month: int = None,
    day: int = None,
    start: str = None,
    end: str = None
):
    print(f"[ANOMALY GET] month={month}, day={day}, start={start}, end={end}")
    try:
        query = "SELECT timestamp, energy_type, route_name, value FROM anomalies WHERE 1=1"
        params = {}
        if month:
            query += " AND EXTRACT(MONTH FROM timestamp) = :month"
            params["month"] = month
        if day:
            query += " AND EXTRACT(DAY FROM timestamp) = :day"
            params["day"] = day
        if start:
            query += " AND timestamp >= :start"
            params["start"] = start
        if end:
            query += " AND timestamp <= :end"
            params["end"] = end
        query += " ORDER BY timestamp DESC LIMIT 100"
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            rows = [dict(r._mapping) for r in result]
        print(f"[ANOMALY GET] Found {len(rows)} rows.")
        return {"data": rows}
    except Exception as e:
        print(f"[ANOMALY GET] ERROR: {e}")
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/forecast")
def forecast_energy(
    energy_type: str = Query(...),
    route_name: str = Query(...)
):
    try:
        # Geçmiş verileri çek (son 1000 kayıt)
        query = "SELECT timestamp, value FROM energy_data WHERE energy_type = :energy_type AND route_name = :route_name ORDER BY timestamp ASC LIMIT 1000"
        params = {"energy_type": energy_type, "route_name": route_name}
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            rows = [dict(r._mapping) for r in result]
        if not rows or len(rows) < 20:
            return {"error": "Yeterli veri yok"}
        df = pd.DataFrame(rows)
        df = df.rename(columns={"timestamp": "ds", "value": "y"})
        # Prophet modeli
        m = Prophet()
        m.fit(df)
        future = m.make_future_dataframe(periods=5, freq='H')
        forecast = m.predict(future)
        # Son 5 tahmini ve trendi döndür
        result = forecast[['ds', 'yhat', 'trend']].tail(5).to_dict(orient='records')
        return {"forecast": result}
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"error": str(e)})

# Socket.IO ASGI app
import uvicorn
from fastapi import Request
from starlette.middleware.wsgi import WSGIMiddleware
from starlette.routing import Mount

# Uvicorn ile çalıştırmak için:
# uvicorn main:app --reload 