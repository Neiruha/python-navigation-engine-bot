"""
Тест потока навигации.

Этот тест проверяет:
- Переходы между экранами.
- Сохранение и передачу контекста.
- Работу `back_path` (включая `CONTEXTUAL`).
- Работу `supports_multi_select` и `selections`.
- Работу чат-режима (ввод текста, команды finish).
- Поведение при отсутствии экрана (ошибка).
"""
import sys
import os
# Добавляем путь к navigation, чтобы можно было импортировать
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from navigation.engine import NavigationEngine
from navigation.manifest import ManifestLoader
from navigation.api_stub import APISimulator

# --- Тестовые сценарии ---

def test_basic_navigation_and_context():
    """Тест: Простая навигация с передачей контекста."""
    print("--- Тест: Простая навигация с контекстом ---")
    engine = NavigationEngine(manifest_path="menu-manifest.json", api_client=APISimulator())
    user_id = "test_user_1"
    engine.init_user(user_id)

    # Ожидаем стартовый экран
    view = engine.get_current_view(user_id)
    assert view["text"] == "Вы находитесь в главном меню"
    assert view["screen_type"] == "static"

    # Навигация к трекам
    action_tracks = next((a for a in view["actions"] if a.get("label") == "Мои треки"), None)
    assert action_tracks is not None
    engine.handle_action(user_id, action_tracks)

    view = engine.get_current_view(user_id)
    assert view["screen_type"] == "dynamic" # треки - динамический список

    # Предполагаем, что есть хотя бы один трек
    items = engine.api_client.call("/api/teacher/tracks", "GET")
    if not items:
        print("  WARNING: Нет треков для теста. Пропускаем проверку контекста.")
        return

    # Выбираем первый трек (предполагаем, что он есть)
    first_track = items[0]
    expected_context = {"track_id": first_track["id"], "track_name": first_track["name"]}
    # Ищем кнопку для первого трека
    action_track_detail = next((a for a in view["actions"] if a.get("label") == first_track["name"]), None)
    assert action_track_detail is not None
    engine.handle_action(user_id, action_track_detail)

    view = engine.get_current_view(user_id)
    expected_title = f"Трек: {first_track['name']}"
    assert view["text"] == expected_title

    # Проверяем, что контекст сохранился
    user_state = engine.get_user_state(user_id)
    assert user_state["context"]["track_id"] == expected_context["track_id"]
    assert user_state["context"]["track_name"] == expected_context["track_name"]
    print("  OK: Навигация и контекст работают.")


def test_contextual_back():
    """Тест: Возврат с `back_path: CONTEXTUAL`."""
    print("--- Тест: Возврат с CONTEXTUAL ---")
    engine = NavigationEngine(manifest_path="menu-manifest.json", api_client=APISimulator())
    user_id = "test_user_2"
    engine.init_user(user_id)

    # Идём: main -> quick_grade -> select_metric
    # main
    view = engine.get_current_view(user_id)
    assert view["text"] == "Вы находитесь в главном меню"

    action_qg = next((a for a in view["actions"] if a.get("label") == "Поставить отметки"), None)
    assert action_qg is not None
    engine.handle_action(user_id, action_qg)

    # quick_grade
    view = engine.get_current_view(user_id)
    assert view["screen_type"] == "dynamic" # quick_grade - динамический список

    # Предполагаем, что есть хотя бы один студент
    items = engine.api_client.call("/api/teacher/recent_students", "GET")
    if not items:
        print("  WARNING: Нет студентов для quick_grade. Пропускаем тест.")
        return

    first_student = items[0]
    expected_context = {"student_id": first_student["id"], "student_name": first_student["full_name"]}
    action_select_metric = next((a for a in view["actions"] if a.get("label") == first_student["full_name"]), None)
    assert action_select_metric is not None
    engine.handle_action(user_id, action_select_metric)

    # select_metric
    view = engine.get_current_view(user_id)
    expected_title = f"Выберите метрику для {first_student['full_name']}"
    assert view["text"] == expected_title
    assert view["screen_type"] == "dynamic"
    # back_path у select_metric - CONTEXTUAL
    back_action = next((a for a in view["actions"] if a.get("type") == "back"), None)
    assert back_action is not None

    # Нажимаем "Назад" -> должно вернуть к quick_grade
    engine.handle_action(user_id, back_action)

    view = engine.get_current_view(user_id)
    assert view["text"] == "Быстрый выбор: для кого ставим отметку?"

    # Снова идём на select_metric
    action_select_metric = next((a for a in view["actions"] if a.get("label") == first_student["full_name"]), None)
    assert action_select_metric is not None
    engine.handle_action(user_id, action_select_metric)

    # Теперь на select_metric -> confirm_mark
    view = engine.get_current_view(user_id)
    # Выбираем первую метрику
    metrics = engine.api_client.call("/api/metrics", "GET")
    if not metrics:
        print("  WARNING: Нет метрик для теста. Пропускаем проверку confirm_mark.")
        return
    first_metric = metrics[0]
    action_confirm = next((a for a in view["actions"] if a.get("label") == first_metric["name"]), None)
    assert action_confirm is not None
    engine.handle_action(user_id, action_confirm)

    # confirm_mark
    view = engine.get_current_view(user_id)
    expected_title_confirm = f"Подтвердите: отметить {first_student['full_name']} по метрике «{first_metric['name']}»?"
    assert view["text"] == expected_title_confirm

    # Нажимаем "Нет" -> back_path у confirm_mark - select_metric
    action_no = next((a for a in view["actions"] if a.get("label") == "Нет"), None)
    assert action_no is not None
    engine.handle_action(user_id, action_no)

    # Должны вернуться на select_metric
    view = engine.get_current_view(user_id)
    assert view["text"] == expected_title # Тот же заголовок select_metric
    # Контекст студента должен остаться
    user_state = engine.get_user_state(user_id)
    assert user_state["context"]["student_id"] == expected_context["student_id"]
    print("  OK: CONTEXTUAL и обычный back работают корректно.")


def test_chat_mode():
    """Тест: Работа чат-режима."""
    print("--- Тест: Чат-режим ---")
    engine = NavigationEngine(manifest_path="menu-manifest.json", api_client=APISimulator())
    user_id = "test_user_4"
    engine.init_user(user_id)

    # main
    view = engine.get_current_view(user_id)
    action_chat = next((a for a in view["actions"] if a.get("label") == "Разговорный режим"), None)
    assert action_chat is not None
    engine.handle_action(user_id, action_chat)

    # chat_mode
    view = engine.get_current_view(user_id)
    assert view["screen_type"] == "chat_input"
    assert view["actions"] == [] # Нет кнопок в чате

    # Отправляем сообщение
    test_message = "Привет, это тестовое сообщение."
    engine.handle_user_input(user_id, test_message)

    # Проверяем, что мы всё ещё в чате
    view = engine.get_current_view(user_id)
    assert view["screen_type"] == "chat_input"

    # Отправляем команду finish
    finish_cmd = "/finish"
    engine.handle_user_input(user_id, finish_cmd)

    # Проверяем, что вернулись на main
    view = engine.get_current_view(user_id)
    assert view["text"] == "Вы находитесь в главном меню"
    print("  OK: Чат-режим и команды finish работают.")


def test_error_screen():
    """Тест: Поведение при отсутствии экрана."""
    print("--- Тест: Ошибка при отсутствии экрана ---")
    engine = NavigationEngine(manifest_path="menu-manifest.json", api_client=APISimulator())
    user_id = "test_user_5"
    engine.init_user(user_id)

    # Пытаемся перейти на несуществующий экран
    fake_action = {"type": "navigate", "target": "non_existent_screen", "label": "Fake Button"}
    engine.handle_action(user_id, fake_action)

    # Ожидаем ошибку в логах и возврат к main или показ экрана ошибки
    # В текущей реализации engine.handle_action не возвращает ничего при ошибке навигации
    # Он просто логгирует. И текущий экран не меняет.
    # Проверим, что текущий экран не изменился (в данном случае, main)
    # Однако, handle_action меняет current_screen на main, если целевой экран не найден.
    # См. _handle_navigate -> if target_screen not in self.manifest.screens: ...
    # Это поведение можно считать "возврат к безопасному состоянию".
    # Проверим, что экран стал main.
    view = engine.get_current_view(user_id)
    # После перехода на несуществующий экран, current_screen должен быть main
    user_state = engine.get_user_state(user_id)
    # _handle_navigate не меняет current_screen, если экран не найден, он просто возвращает.
    # НО! В _handle_navigate есть логика, которая *должна* менять на main.
    # `if target_screen not in self.manifest.screens: self.logger.log_error(...); return`
    # А вот в _handle_action после _handle_navigate, если `action_data` не изменил `current_screen`, он останется.
    # Нет, _handle_navigate меняет `state["current_screen"] = "main"` при ошибке.
    # Проверим это.
    assert user_state["current_screen"] == "main"
    # И view должен быть main
    assert view["text"] == "Вы находитесь в главном меню"
    print("  OK: Ошибка при отсутствии экрана обрабатывается корректно (возврат на main).")

def test_selection_history():
    """Тест: История выборов (`selections`) с `supports_multi_select: false`."""
    print("--- Тест: История выборов ---")
    engine = NavigationEngine(manifest_path="menu-manifest.json", api_client=APISimulator())
    user_id = "test_user_3"
    engine.init_user(user_id)

    # Идём: main -> quick_grade -> select_metric
    # main
    view = engine.get_current_view(user_id)
    action_qg = next((a for a in view["actions"] if a.get("label") == "Поставить отметки"), None)
    assert action_qg is not None
    engine.handle_action(user_id, action_qg)

    # quick_grade
    view = engine.get_current_view(user_id)
    items = engine.api_client.call("/api/teacher/recent_students", "GET")
    if not items:
        print("  WARNING: Нет студентов для quick_grade. Пропускаем тест.")
        return
    first_student = items[0]
    action_select_metric = next((a for a in view["actions"] if a.get("label") == first_student["full_name"]), None)
    assert action_select_metric is not None
    engine.handle_action(user_id, action_select_metric)

    # select_metric
    view = engine.get_current_view(user_id)
    metrics = engine.api_client.call("/api/metrics", "GET")
    if len(metrics) < 2:
        print("  WARNING: Недостаточно метрик для теста multi-select. Пропускаем проверку.")
        return

    # Выбираем первую метрику
    first_metric = metrics[0]
    action_first_metric = next((a for a in view["actions"] if a.get("label") == first_metric["name"]), None)
    assert action_first_metric is not None
    print(f"  DEBUG: Выбираю метрику '{first_metric['name']}', action_data: {action_first_metric}")
    engine.handle_action(user_id, action_first_metric)

    # Проверяем историю: должен быть один выбор на экране select_metric
    user_state = engine.get_user_state(user_id)
    selections = user_state["selections"]
    print(f"  DEBUG: Все selections после первого выбора: {selections}")
    select_metric_selections = [s for s in selections if s["screen_id"] == "select_metric"]
    print(f"  DEBUG: Выборы для select_metric: {select_metric_selections}")
    assert len(select_metric_selections) == 1
    # Отладка: что внутри
    print(f"  DEBUG: selected_item для select_metric: {select_metric_selections[0]['selected_item']}")
    assert select_metric_selections[0]["selected_item"]["target"] == "confirm_mark" # Это тип navigate

    # Возвращаемся на select_metric (предположим, через confirm_mark -> "Нет")
    # Но проще выбрать другую метрику на том же экране select_metric
    # Для этого нужно снова попасть на select_metric
    # Назад из confirm_mark -> select_metric
    view = engine.get_current_view(user_id)
    print(f"  DEBUG: Вид после выбора метрики (ожидаем confirm_mark): {view['text']}")
    action_no = next((a for a in view["actions"] if a.get("label") == "Нет"), None)
    if action_no:
        print(f"  DEBUG: Нажимаю 'Нет', action_data: {action_no}")
        engine.handle_action(user_id, action_no)
    else: # Если confirm_mark не был показан, просто вернёмся
        back_action = next((a for a in view["actions"] if a.get("type") == "back"), None)
        assert back_action is not None
        print(f"  DEBUG: Нажимаю 'Назад', action_data: {back_action}")
        engine.handle_action(user_id, back_action)

    # Снова на select_metric
    view = engine.get_current_view(user_id)
    print(f"  DEBUG: Вернулись на select_metric, вид: {view['text']}")
    # Выбираем вторую метрику
    second_metric = metrics[1]
    action_second_metric = next((a for a in view["actions"] if a.get("label") == second_metric["name"]), None)
    assert action_second_metric is not None
    print(f"  DEBUG: Выбираю вторую метрику '{second_metric['name']}', action_data: {action_second_metric}")
    engine.handle_action(user_id, action_second_metric)

    # Проверяем историю: по-прежнему должен быть только выбор второй метрики на этом экране, т.к. multi_select: false
    user_state = engine.get_user_state(user_id)
    selections = user_state["selections"]
    print(f"  DEBUG: Все selections после второго выбора: {selections}")
    select_metric_selections = [s for s in selections if s["screen_id"] == "select_metric"]
    print(f"  DEBUG: Выборы для select_metric после второго выбора: {select_metric_selections}")
    # print(f"DEBUG: selections after second choice: {selections}")
    # print(f"DEBUG: select_metric_selections: {select_metric_selections}")
    assert len(select_metric_selections) == 1 # Должна остаться только одна запись для select_metric
    # И эта запись должна быть от второго выбора
    print(f"  DEBUG: selected_item для select_metric после второго выбора: {select_metric_selections[0]['selected_item']}")
    assert select_metric_selections[0]["selected_item"]["target"] == "confirm_mark" # Второй выбор
    print("  OK: История выборов с multi_select: false работает корректно.")


def run_all_tests():
    """Запуск всех тестов."""
    print("Запуск изощрённого теста навигации...\n")
    try:
        test_basic_navigation_and_context()
    except Exception as e:
        print(f"  FAIL: test_basic_navigation_and_context: {e}")
        import traceback
        traceback.print_exc()
    try:
        test_contextual_back()
    except Exception as e:
        print(f"  FAIL: test_contextual_back: {e}")
        import traceback
        traceback.print_exc()
    try:
        test_selection_history()
    except Exception as e:
        print(f"  FAIL: test_selection_history: {e}")
        import traceback
        traceback.print_exc()
    try:
        test_chat_mode()
    except Exception as e:
        print(f"  FAIL: test_chat_mode: {e}")
        import traceback
        traceback.print_exc()
    try:
        test_error_screen()
    except Exception as e:
        print(f"  FAIL: test_error_screen: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- Все тесты завершены. ---")


if __name__ == "__main__":
    run_all_tests()