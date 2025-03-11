from fastapi import FastAPI
from pydantic import BaseModel
from .models import Base
from .database import engine
from .routers import devices, farms, crops


app = FastAPI(root_path='/api/device-service')

Base.metadata.create_all(bind=engine)


app.include_router(devices.router)
app.include_router(farms.router)
app.include_router(crops.router)


@app.get('/health')
async def health_check():
    return {'health': 'ok'}