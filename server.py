from aiohttp import web
import jwt
import json
from pydantic import ValidationError
from models import (
    Session, Ad, User, init_db, hash_password, check_password,
    create_token, SECRET_KEY, ALGORITHM, AdCreateSchema, AdUpdateSchema, UserSchema
)
from sqlalchemy import select


# Middleware для авторизации по JWT
@web.middleware
async def auth_middleware(request: web.Request, handler):
    token = request.headers.get("Authorization")
    request["user_id"] = None

    if token:
        try:
            # Ожидаем формат "Bearer <token>"
            if token.startswith("Bearer "):
                token = token.split(" ")[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            request["user_id"] = payload["user_id"]
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass  # Если токен плохой, user_id останется None

    return await handler(request)


@web.middleware
async def session_middleware(request: web.Request, handler):
    async with Session() as session:
        request["session"] = session
        return await handler(request)


# --- Обработчики ---

async def register(request: web.Request):
    try:
        data = await request.json()
        validated_data = UserSchema(**data)
        session = request["session"]

        new_user = User(email=validated_data.email, password=hash_password(validated_data.password))
        session.add(new_user)
        await session.commit()
        return web.json_response({"id": new_user.id})
    except ValidationError as e:
        return web.json_response(e.errors(), status=400)
    except Exception:
        return web.json_response({"error": "user already exists"}, status=409)


async def login(request: web.Request):
    data = await request.json()
    session = request["session"]
    query = select(User).where(User.email == data["email"])
    result = await session.execute(query)
    user = result.scalar()

    if user and check_password(data["password"], user.password):
        token = create_token(user.id)
        return web.json_response({"token": token})
    return web.json_response({"error": "bad login"}, status=401)


class AdView(web.View):
    async def get_ad(self):
        ad_id = int(self.request.match_info["ad_id"])
        ad = await self.request["session"].get(Ad, ad_id)
        if not ad:
            raise web.HTTPNotFound(text=json.dumps({"error": "not found"}), content_type="application/json")
        return ad

    def check_owner(self, ad):
        if not self.request["user_id"] or ad.owner_id != self.request["user_id"]:
            raise web.HTTPForbidden(text=json.dumps({"error": "forbidden"}), content_type="application/json")

    async def get(self):
        ad = await self.get_ad()
        return web.json_response({
            "id": ad.id, "title": ad.title, "description": ad.description,
            "owner_id": ad.owner_id, "created_at": ad.created_at.isoformat()
        })

    async def post(self):
        if not self.request["user_id"]:
            raise web.HTTPUnauthorized()

        try:
            data = await self.request.json()
            validated = AdCreateSchema(**data)
            new_ad = Ad(**validated.dict(), owner_id=self.request["user_id"])
            self.request["session"].add(new_ad)
            await self.request["session"].commit()
            return web.json_response({"id": new_ad.id})
        except ValidationError as e:
            return web.json_response(e.errors(), status=400)

    async def patch(self):
        ad = await self.get_ad()
        self.check_owner(ad)

        try:
            data = await self.request.json()
            validated = AdUpdateSchema(**data)

            # Обновляем только те поля, которые прислали
            for key, value in validated.dict(exclude_unset=True).items():
                setattr(ad, key, value)

            await self.request["session"].commit()
            return web.json_response({"status": "updated"})
        except ValidationError as e:
            return web.json_response(e.errors(), status=400)

    async def delete(self):
        ad = await self.get_ad()
        self.check_owner(ad)
        await self.request["session"].delete(ad)
        await self.request["session"].commit()
        return web.json_response({"status": "deleted"})


app = web.Application(middlewares=[session_middleware, auth_middleware])


async def on_startup(app):
    await init_db()


app.on_startup.append(on_startup)
app.add_routes([
    web.post("/register", register),
    web.post("/login", login),
    web.post("/ads", AdView),
    web.get("/ads/{ad_id:\d+}", AdView),
    web.patch("/ads/{ad_id:\d+}", AdView),  # Добавили PATCH
    web.delete("/ads/{ad_id:\d+}", AdView),
])

if __name__ == "__main__":
    web.run_app(app)