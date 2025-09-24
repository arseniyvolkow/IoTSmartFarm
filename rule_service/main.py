from fastapi import FastAPI
from .models import Base
from .database import engine
from contextlib import asynccontextmanager
from .routers import rules


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


app = FastAPI(root_path="/api/rule-service", lifespan=lifespan)



app.include_router(rules.router)


@app.get("/health")
async def health_check():
    return {"health": "ok"}
