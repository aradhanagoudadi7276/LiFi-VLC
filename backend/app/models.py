import datetime
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime
from .database import Base

class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    bit_time = Column(Float, default=0.2)
    led_pin = Column(Integer, default=18)
    adc_channel = Column(Integer, default=0)
    spi_port = Column(Integer, default=0)
    spi_device = Column(Integer, default=0)
    spi_speed = Column(Integer, default=1350000)
    threshold_voltage = Column(Float, default=1.65)
    noise_level = Column(Float, default=0.0)  # 0.0 (clean) to 1.0 (pure noise)
    use_mock = Column(Boolean, default=True)

class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, index=True)
    direction = Column(String)  # "SENT" or "RECEIVED"
    text = Column(String)
    binary_data = Column(String)  # Raw binary bits representation
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String)  # "SUCCESS", "FAILED", "IN_PROGRESS"
