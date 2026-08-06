from contextlib import asynccontextmanager

from fastapi import FastAPI

from user_service.database import engine
from user_service.routers import admin, auth, user


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


app = FastAPI(root_path="/api/user-service", lifespan=lifespan)


app.include_router(admin.router)
app.include_router(user.router)
app.include_router(auth.router)
