from fastapi import FastAPI
from common.rule_models import Base
from rule_service.database import engine
from contextlib import asynccontextmanager
from rule_service.routers import rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    print("Application startup: Alembic handles migrations.")

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
