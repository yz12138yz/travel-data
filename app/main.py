from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from .config import APP_PORT
from .dialogue.router import router as dialogue_router
from .dialogue.tables import ensure_tables
from .routers.marketing import router as marketing_router
from .routers.orders import router as orders_router
from .routers.products import router as products_router
from .routers.refunds import router as refunds_router
from .routers.users import router as users_router

OPENAPI_TAGS = [
    {"name": "users", "description": "1. 用户中心与会员信息"},
    {"name": "products", "description": "2. 商品搜索、详情与价格查询"},
    {"name": "marketing", "description": "3. 营销与优惠券"},
    {"name": "orders", "description": "4. 交易、订单与支付"},
    {"name": "refunds", "description": "5. 售后与退款"},
    {"name": "dialogue", "description": "6. 旅游智能客服对话系统"},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    # 应用启动时幂等创建对话系统所需表（会话 / 消息 / 工单）
    ensure_tables()
    yield


app = FastAPI(
    title="Travel Data API",
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.include_router(users_router)
app.include_router(products_router)
app.include_router(marketing_router)
app.include_router(orders_router)
app.include_router(refunds_router)
app.include_router(dialogue_router)

_DEMO_HTML = Path(__file__).resolve().parent / "dialogue" / "static" / "index.html"


@app.exception_handler(ValueError)
async def handle_value_error(_, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dialogue-demo", include_in_schema=False)
def dialogue_demo() -> FileResponse:
    """前端调试 / 演示页面。"""
    return FileResponse(_DEMO_HTML)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=APP_PORT, reload=False)
