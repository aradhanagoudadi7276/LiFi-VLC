from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class SettingsBase(BaseModel):
    bit_time: float = Field(default=0.2, ge=0.01, le=5.0)
    led_pin: int = Field(default=18, ge=0, le=40)
    adc_channel: int = Field(default=0, ge=0, le=7)
    spi_port: int = Field(default=0, ge=0, le=2)
    spi_device: int = Field(default=0, ge=0, le=2)
    spi_speed: int = Field(default=1350000, ge=100000, le=20000000)
    threshold_voltage: float = Field(default=1.65, ge=0.0, le=3.3)
    noise_level: float = Field(default=0.0, ge=0.0, le=1.0)
    use_mock: bool = Field(default=True)

class SettingsUpdate(SettingsBase):
    pass

class SettingsResponse(SettingsBase):
    id: int

    class Config:
        from_attributes = True

class MessageLogBase(BaseModel):
    direction: str
    text: str
    binary_data: str
    status: str

class MessageLogResponse(MessageLogBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class TransmitRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
