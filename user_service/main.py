from fastapi import FastAPI
from user_service.database import engine
from user_service.models import Base
from user_service.routers import user, admin, auth
from contextlib import asynccontextmanager


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


app = FastAPI(root_path="/api/user-service", lifespan=lifespan)


app.include_router(admin.router)
app.include_router(user.router)
app.include_router(auth.router)
