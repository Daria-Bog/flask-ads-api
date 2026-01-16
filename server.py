from aiohttp import web
from models import Session, Ad, User, init_db, hash_password, check_password
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json


# Middleware для управления сессиями БД
@web.middleware
async def session_middleware(request: web.Request, handler):
    async with Session() as session:
        request["session"] = session
        return await handler(request)


# --- Хендлеры для Пользователей ---

async def register(request: web.Request):
    data = await request.json()
    session = request["session"]
    # Хешируем пароль перед сохранением
    data["password"] = hash_password(data["password"])
    new_user = User(**data)
    try:
        session.add(new_user)
        await session.commit()
    except Exception:
        raise web.HTTPConflict(text=json.dumps({"error": "user already exists"}), content_type="application/json")
    return web.json_response({"id": new_user.id})


async def login(request: web.Request):
    data = await request.json()
    session = request["session"]
    query = select(User).where(User.email == data["email"])
    result = await session.execute(query)
    user = result.scalar()

    if user and check_password(data["password"], user.password):
        # В учебных целях просто возвращаем ID как "токен"
        return web.json_response({"token": str(user.id)})
    raise web.HTTPUnauthorized(text=json.dumps({"error": "bad login"}), content_type="application/json")


# --- Класс-вью для Объявлений ---

class AdView(web.View):
    @property
    def session(self) -> AsyncSession:
        return self.request["session"]

    async def get_ad(self):
        ad_id = int(self.request.match_info["ad_id"])
        ad = await self.session.get(Ad, ad_id)
        if not ad:
            raise web.HTTPNotFound(text=json.dumps({"error": "ad not found"}), content_type="application/json")
        return ad

    async def get(self):
        ad = await self.get_ad()
        return web.json_response({
            "id": ad.id, "title": ad.title, "description": ad.description,
            "owner_id": ad.owner_id, "created_at": ad.created_at.isoformat()
        })

    async def post(self):
        # Задание 2: Проверка прав (кто владелец?)
        token = self.request.headers.get("Authorization")
        if not token:
            raise web.HTTPForbidden(text="Token required")

        data = await self.request.json()
        data["owner_id"] = int(token)  # Используем наш "токен" как ID владельца
        new_ad = Ad(**data)
        self.session.add(new_ad)
        await self.session.commit()
        return web.json_response({"id": new_ad.id})

    async def delete(self):
        token = self.request.headers.get("Authorization")
        ad = await self.get_ad()
        if ad.owner_id != int(token):
            raise web.HTTPForbidden(text="You are not the owner")

        await self.session.delete(ad)
        await self.session.commit()
        return web.json_response({"status": "deleted"})


# --- Настройка приложения ---

app = web.Application(middlewares=[session_middleware])


async def on_startup(app):
    await init_db()


app.on_startup.append(on_startup)

app.add_routes([
    web.post("/register", register),
    web.post("/login", login),
    web.post("/ads", AdView),
    web.get("/ads/{ad_id:\d+}", AdView),
    web.delete("/ads/{ad_id:\d+}", AdView),
])

if __name__ == "__main__":
    web.run_app(app)