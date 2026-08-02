from common.rule_database import Base, engine, AsyncSessionLocal

async def get_db():
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()