import asyncio
import aiohttp

async def main():
    async with aiohttp.ClientSession() as session:
        # 1. Регистрация
        async with session.post('http://localhost:8080/register',
                                json={"email": "test@mail.com", "password": "secret_pass"}) as resp:
            print(f"Регистрация: {resp.status}, {await resp.json()}")

        # 2. Логин
        async with session.post('http://localhost:8080/login',
                                json={"email": "test@mail.com", "password": "secret_pass"}) as resp:
            data = await resp.json()
            token = data.get("token")
            print(f"Логин: {resp.status}, получен токен: {token}")

        headers = {"Authorization": token}

        # 3. Создание объявления
        async with session.post('http://localhost:8080/ads',
                                json={"title": "Продам кота", "description": "Кот ученый"},
                                headers=headers) as resp:
            ad_data = await resp.json()
            ad_id = ad_data.get("id")
            print(f"Создание: {resp.status}, ID: {ad_id}")

        # 4. Получение объявления
        async with session.get(f'http://localhost:8080/ads/{ad_id}') as resp:
            print(f"Получение: {resp.status}, Данные: {await resp.json()}")

if __name__ == '__main__':
    asyncio.run(main())