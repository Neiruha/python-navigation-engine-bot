# navigation/api_stub.py
from typing import Any, Dict, List
import json

class APISimulator:
    """
    Умная заглушка для внешних API.
    Легко расширить: просто добавь ключ в MOCK_DATA.
    В продакшене — замени на requests/aiohttp.
    """
    MOCK_DATA = {
        "/api/teacher/tracks": [
            {"id": "game-design", "name": "Геймдизайн"},
            {"id": "architecture", "name": "Архитектура"},
        ],
        "/api/metrics": [
            {"id": "creative", "name": "Креативность"},
            {"id": "result", "name": "Результат"},
            {"id": "teamwork", "name": "Работа в команде"},
            {"id": "initiative", "name": "Инициативность"},
            {"id": "discipline", "name": "Дисциплина"},
            {"id": "communication", "name": "Коммуникация"},
            {"id": "problem_solving", "name": "Решение проблем"},
            {"id": "leadership", "name": "Лидерство"},
            {"id": "adaptability", "name": "Адаптивность"},
            {"id": "accuracy", "name": "Точность"},
            {"id": "persistence", "name": "Настойчивость"},
            {"id": "ethics", "name": "Этичность"},
        ],
        "/api/tracks/game-design/students": [
            {"id": "ivanov", "full_name": "Иванов Иван"},
            {"id": "petrov", "full_name": "Петров Пётр"},
        ],
        "/api/tracks/architecture/students": [
            {"id": "sidorov", "full_name": "Сидоров Сидор"},
        ],
        "/api/teacher/recent_students": [
            {"id": "ivanov", "full_name": "Иванов Иван"},
            {"id": "sidorov", "full_name": "Сидоров Сидор"},
        ]
    }

    def call(self, url: str, method: str = "GET", **kwargs) -> List[Dict[str, Any]]:
        """
        Имитирует API-вызов.
        :param url: путь (может содержать шаблоны, например /api/tracks/{{track_id}}/students)
        :param method: HTTP-метод (игнорируется в заглушке)
        :return: список объектов
        """
        # 🔥 ОПАСНОЕ МЕСТО: если URL не найден — упадём!
        # В продакшене: оберни в try/except и верни пустой список или ошибку
        if url in self.MOCK_DATA:
            return self.MOCK_DATA[url]
        
        # Попытка найти "по шаблону" (упрощённо)
        # Например: /api/tracks/game-design/students → ищем по базовому пути
        for key in self.MOCK_DATA:
            if key.startswith("/api/tracks/") and key.endswith("/students"):
                if url.startswith("/api/tracks/") and url.endswith("/students"):
                    return self.MOCK_DATA[key]  # возвращаем первый подходящий

        # Если ничего не найдено — логгируем и возвращаем пустой список
        return []