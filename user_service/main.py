from fastapi import FastAPI
from .database import engine
from .models import Base
from .routers import auth, user, admin


app = FastAPI()

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(admin.router)