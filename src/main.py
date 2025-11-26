from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.v1.routes import auth, users, billing, regos, tokens, system, ai, click, lang
from src.core.conf import ENVIRONMENT
from src.core.lifespan import lifespan
from src.core.logger import setup_logger

logger = setup_logger()
logger.info("Application starting...")

# FastAPI app
app = FastAPI(
    title="DocVision",
    description="DocVision - Extracting invoice file and load to Regos system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


if ENVIRONMENT == "development":
    # Development
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(tokens.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(regos.router, prefix="/api/v1")
    app.include_router(ai.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(lang.router, prefix="/api/v1")
    app.include_router(click.router, prefix="/api")
else:
    # Production
    app.include_router(auth.router, prefix="/v1")
    app.include_router(users.router, prefix="/v1")
    app.include_router(tokens.router, prefix="/v1")
    app.include_router(billing.router, prefix="/v1")
    app.include_router(regos.router, prefix="/v1")
    app.include_router(ai.router, prefix="/v1")
    app.include_router(system.router, prefix="/v1")
    app.include_router(lang.router, prefix="/v1")
    app.include_router(click.router, prefix="")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)