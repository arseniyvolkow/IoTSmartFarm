from fastapi import FastAPI
from pydantic import BaseModel
from .models import Base
from .database import engine
from contextlib import asynccontextmanager
from .routers import devices, farms, crops


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Application startup: Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created or already exist.")

    # Yield control to the application
    yield

    # Shutdown logic (executed after the application stops receiving requests)
    print("Application shutdown: Disposing database engine...")
    await engine.dispose()
    print("Database engine disposed.")


app = FastAPI(root_path="/api/device-service", lifespan=lifespan)


app.include_router(devices.router)
app.include_router(farms.router)
app.include_router(crops.router)


@app.get("/health")
async def health_check():
    return {"health": "ok"}
