from flask import Flask, request
from flask_restful import Resource, Api, reqparse
from flask_cors import CORS
import datetime
import uuid
import json

# --- 1. Импорт для Аутентификации ---
from passlib.hash import pbkdf2_sha256
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager

# --- 2. Инициализация Flask и API ---
app = Flask(__name__)
CORS(app)
api = Api(app)

# Настройка JWT
# В реальном проекте этот секретный ключ должен быть сложным и храниться в переменных окружения!
app.config["JWT_SECRET_KEY"] = "super-secret-key-for-ads-api-v2"
# Время жизни токена (например, 30 минут)
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(minutes=30)
jwt = JWTManager(app)

# --- 3. Имитация базы данных: Объявления и Пользователи ---
# Структура: {id: {id: str, title: str, description: str, created_at: str, owner_id: str}}
ADS = {}
# Структура: {user_id: {id: str, email: str, password_hash: str}}
USERS = {}
# Используем счетчик для упрощения user_id
USER_ID_COUNTER = 1


# --- 4. Вспомогательные функции ---

def serialize_ad(ad_data):
    """Преобразует данные объявления в формат, удобный для JSON-ответа."""
    # Возвращаем ID владельца, а не его почту или хеш
    return {
        'id': ad_data['id'],
        'title': ad_data['title'],
        'description': ad_data['description'],
        'created_at': ad_data['created_at'],
        'owner_id': ad_data['owner_id']
    }


def get_user_id_by_email(email):
    """Находит ID пользователя по его почте."""
    for user_id, user_data in USERS.items():
        if user_data['email'] == email:
            return user_id
    return None


# --- 5. Ресурсы для Аутентификации (Register & Login) ---

class UserRegister(Resource):
    """Регистрация нового пользователя."""

    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('email', type=str, required=True, help="Email обязателен")
        parser.add_argument('password', type=str, required=True, help="Пароль обязателен")
        args = parser.parse_args()

        if get_user_id_by_email(args['email']):
            return {"message": "Пользователь с таким email уже существует"}, 400

        global USER_ID_COUNTER
        user_id = str(USER_ID_COUNTER)
        USER_ID_COUNTER += 1

        # Хеширование пароля перед сохранением
        password_hash = pbkdf2_sha256.hash(args['password'])

        user_data = {
            'id': user_id,
            'email': args['email'],
            'password_hash': password_hash
        }

        USERS[user_id] = user_data

        return {"message": f"Пользователь {args['email']} успешно зарегистрирован", "user_id": user_id}, 201


class UserLogin(Resource):
    """Вход пользователя и выдача JWT-токена."""

    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('email', type=str, required=True, help="Email обязателен")
        parser.add_argument('password', type=str, required=True, help="Пароль обязателен")
        args = parser.parse_args()

        user_id = get_user_id_by_email(args['email'])

        if not user_id:
            return {"message": "Неправильный email или пароль"}, 401

        user = USERS[user_id]

        # Проверка хеша пароля
        if pbkdf2_sha256.verify(args['password'], user['password_hash']):
            # Создание токена доступа.
            # Идентификатор, который мы сохраняем в токене - это user_id
            access_token = create_access_token(identity=user_id)
            return {"access_token": access_token}, 200
        else:
            return {"message": "Неправильный email или пароль"}, 401


# --- 6. Защищенные Ресурсы для Объявлений ---

class Ad(Resource):
    """
    Реализует GET, PUT, DELETE для одного объявления.
    PUT и DELETE теперь защищены.
    """

    def get(self, ad_id):
        """Получает объявление по ID (публичный доступ)."""
        if ad_id not in ADS:
            return {"message": "Объявление не найдено"}, 404
        return serialize_ad(ADS[ad_id])

    @jwt_required()
    def put(self, ad_id):
        """Редактирует объявление (требуется JWT и право владельца)."""
        current_user_id = get_jwt_identity()

        if ad_id not in ADS:
            return {"message": "Объявление не найдено"}, 404

        ad = ADS[ad_id]

        # Проверка: Только владелец может редактировать объявление
        if ad['owner_id'] != current_user_id:
            return {"message": "У вас нет прав для редактирования этого объявления"}, 403  # 403 Forbidden

        # Парсер для проверки входящих данных
        parser = reqparse.RequestParser()
        parser.add_argument('title', type=str, required=True, help="Заголовок обязателен")
        parser.add_argument('description', type=str, required=True, help="Описание обязательно")

        args = parser.parse_args()

        # Обновляем данные, owner_id и created_at не меняем
        ad['title'] = args['title']
        ad['description'] = args['description']

        return serialize_ad(ad), 200

    @jwt_required()
    def delete(self, ad_id):
        """Удаляет объявление (требуется JWT и право владельца)."""
        current_user_id = get_jwt_identity()

        if ad_id not in ADS:
            return {"message": "Объявление не найдено"}, 404

        ad = ADS[ad_id]

        # Проверка: Только владелец может удалять объявление
        if ad['owner_id'] != current_user_id:
            return {"message": "У вас нет прав для удаления этого объявления"}, 403  # 403 Forbidden

        del ADS[ad_id]
        return "", 204


class AdList(Resource):
    """
    Реализует POST (создание, защищено) и GET (список, публичный доступ).
    """

    @jwt_required()
    def post(self):
        """Создает новое объявление (требуется JWT)."""
        # Получаем ID пользователя из токена
        current_user_id = get_jwt_identity()

        parser = reqparse.RequestParser()
        parser.add_argument('title', type=str, required=True, help="Заголовок обязателен")
        parser.add_argument('description', type=str, required=True, help="Описание обязательно")

        args = parser.parse_args()

        ad_id = str(uuid.uuid4())  # Генерация уникального ID

        new_ad = {
            'id': ad_id,
            'title': args['title'],
            'description': args['description'],
            'created_at': datetime.datetime.now().isoformat(),
            'owner_id': current_user_id  # Владелец берется из токена!
        }

        ADS[ad_id] = new_ad
        return serialize_ad(new_ad), 201

    def get(self):
        """Возвращает список всех объявлений (публичный доступ)."""
        return [serialize_ad(ad) for ad in ADS.values()]


# --- 7. Назначение Роутов ---

api.add_resource(UserRegister, '/auth/register')  # Регистрация
api.add_resource(UserLogin, '/auth/login')  # Вход
api.add_resource(AdList, '/ads')  # POST (защищен) и GET (публичный)
api.add_resource(Ad, '/ads/<string:ad_id>')  # GET (публичный), PUT/DELETE (защищены)

if __name__ == '__main__':
    app.run(debug=True)