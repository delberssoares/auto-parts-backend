from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.db.session import get_db
from app.routers import auth, products

app = FastAPI(title="DSS Auto Peças API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Todo erro volta como {"detail": "mensagem"}, o que o front já sabe exibir
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, **exc.extra},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = [
        {
            "field": ".".join(str(p) for p in e["loc"][1:]),
            "message": e["msg"].removeprefix("Value error, "),
        }
        for e in exc.errors()
    ]
    detail = errors[0]["message"] if errors else "Dados inválidos"
    return JSONResponse(status_code=422, content={"detail": detail, "errors": errors})


app.include_router(auth.router)
app.include_router(products.categories_router)
app.include_router(products.router)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    return {"status": "ok", "database": "connected"}



