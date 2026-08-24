import asyncio
import logging
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import engine, Base, get_db, SessionLocal
from .models import Settings, MessageLog
from .schemas import SettingsUpdate, SettingsResponse, TransmitRequest, MessageLogResponse
from .websocket_manager import ws_manager
from .transmitter_worker import tx_worker
from .receiver_worker import rx_worker

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LiFi System Controller API",
    description="Enterprise REST and WebSocket interface for controlling LED-based LiFi hardware."
)

# Enable CORS for full React frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initializes default settings in SQLite database and starts the background receiver."""
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings:
            settings = Settings()
            db.add(settings)
            db.commit()
            logger.info("Initialized default Settings entry in SQLite.")
        
        # Start receiver by default on startup (gives immediate visual response on frontend)
        loop = asyncio.get_running_loop()
        rx_worker.start(loop)
        logger.info("Background receiver listener auto-started on server launch.")
    except Exception as e:
        logger.error(f"Error during startup database configuration: {e}")
    finally:
        db.close()


@app.on_event("shutdown")
def shutdown_event():
    """Stops all running hardware polling loops on app shutdown."""
    logger.info("Terminating all hardware controller loops...")
    rx_worker.stop()


# Settings Controller API
@app.get("/api/settings", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    settings = db.query(Settings).first()
    if not settings:
        settings = Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@app.put("/api/settings", response_model=SettingsResponse)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    settings = db.query(Settings).first()
    if not settings:
        settings = Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
        
    for var, val in vars(payload).items():
        setattr(settings, var, val)
        
    db.commit()
    db.refresh(settings)
    logger.info("LiFi Settings modified via API request.")
    return settings


# Message logs API
@app.get("/api/messages", response_model=list[MessageLogResponse])
def get_messages(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(MessageLog).order_by(MessageLog.timestamp.desc()).limit(limit).all()


# Transmission Controller API
@app.post("/api/transmit")
async def transmit_message(payload: TransmitRequest):
    if tx_worker.is_transmitting:
        raise HTTPException(
            status_code=400, 
            detail="Transmitter is busy sending another message."
        )
        
    loop = asyncio.get_running_loop()
    try:
        tx_worker.transmit(payload.message, loop)
        return {
            "status": "SUCCESS", 
            "detail": f"Transmission queue accepted: '{payload.message}'"
        }
    except Exception as e:
        logger.error(f"Failed to submit message to transmitter thread: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Transmission trigger failure: {str(e)}"
        )


# Receiver Controller API
@app.post("/api/receiver/start")
async def start_receiver():
    if rx_worker.is_running:
        return {"status": "ALREADY_RUNNING", "detail": "Receiver loop is already active."}
    loop = asyncio.get_running_loop()
    rx_worker.start(loop)
    return {"status": "STARTED", "detail": "Background receiver initialized."}


@app.post("/api/receiver/stop")
def stop_receiver():
    if not rx_worker.is_running:
        return {"status": "ALREADY_STOPPED", "detail": "Receiver is not active."}
    rx_worker.stop()
    return {"status": "STOPPED", "detail": "Background receiver suspended."}


@app.get("/api/receiver/status")
def get_receiver_status():
    return {
        "is_running": rx_worker.is_running
    }


# Live Broadcast WebSocket
@app.websocket("/ws/lifi")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Maintain connection, handle ping/pongs implicitly
            # Wait for client input (typically none needed since this is a read-only stream)
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket client loop exception: {e}")
        ws_manager.disconnect(websocket)
