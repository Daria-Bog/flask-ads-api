import asyncio
import aiohttp

async def main():
    async with aiohttp.ClientSession() as session:
        # 1. Регистрация (теперь с валидацией)
        await session.post('http://localhost:8080/register',
                           json={"email": "daria@mail.com", "password": "mypassword"})

        # 2. Логин -> Получаем настоящий JWT
        async with session.post('http://localhost:8080/login',
                                json={"email": "daria@mail.com", "password": "mypassword"}) as resp:
            token = (await resp.json())["token"]

        headers = {"Authorization": f"Bearer {token}"}

        # 3. Создание
        async with session.post('http://localhost:8080/ads',
                                json={"title": "New Ad", "description": "Good item"},
                                headers=headers) as resp:
            ad_id = (await resp.json())["id"]

        # 4. PATCH (Обновление)
        async with session.patch(f'http://localhost:8080/ads/{ad_id}',
                                 json={"title": "Updated Title"},
                                 headers=headers) as resp:
            print(f"Обновление: {resp.status}")

        # 5. Получение
        async with session.get(f'http://localhost:8080/ads/{ad_id}') as resp:
            print(f"Итог: {await resp.json()}")

if __name__ == '__main__':
    asyncio.run(main())