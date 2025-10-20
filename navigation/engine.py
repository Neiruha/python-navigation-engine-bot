import copy
import time
from typing import Any, Dict, List, Optional, Union
from .logger import NavigationLogger
from .api_stub import APISimulator
from .manifest import ManifestLoader

class NavigationEngine:
    def __init__(
        self,
        manifest_path: str = "menu-manifest.json",
        logger: Optional[NavigationLogger] = None,
        api_client: Optional[Any] = None
    ):
        self.manifest = ManifestLoader(manifest_path)
        self.logger = logger or NavigationLogger()
        self.api_client = api_client or APISimulator()
        self._user_states: Dict[str, Dict[str, Any]] = {}

    def init_user(self, user_id: str):
        self._user_states[user_id] = {
            "current_screen": "main",
            "context": {"user_id": user_id},
            "return_stack": [],
            "pagination": {},
            "selections": [] # <-- Новое поле для истории выборов
        }
        self.logger.log_view_rendered(user_id, "main", "Инициализация")

    def get_user_state(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self._user_states:
            self.init_user(user_id)
        return self._user_states[user_id]

    def get_current_view(self, user_id: str) -> Dict[str, Any]:
        state = self.get_user_state(user_id)
        screen_id = state["current_screen"]
        screen_def = self.manifest.screens.get(screen_id)

        if not screen_def:
            self.logger.log_error(f"Экран не найден: {screen_id}")
            return {
                "text": "Ошибка: экран не найден",
                "actions": [{"id": "back", "label": "< Назад", "type": "back"}],
                "screen_type": "error"
            }

        title = self._render_template(screen_def["title"], state["context"])

        # Обработка чата: возвращаем специальный тип
        if screen_def["type"] == "chat_input":
            # Возвращаем текст и тип, но без кнопок
            # GUI должен отобразить Input и обработать команды
            self.logger.log_view_rendered(user_id, screen_id, title)
            return {"text": title, "actions": [], "screen_type": "chat_input"}

        if screen_def["type"] == "dynamic":
            actions = self._build_dynamic_actions(user_id, screen_def, state["context"])
        elif screen_def.get("paginated"):
            actions = self._build_paginated_actions(user_id, screen_def, state["context"])
        else:
            actions = self._build_static_actions(screen_def)

        back_path = screen_def.get("back_path")
        if back_path:
            back_label = screen_def.get("back_label", self.manifest.defaults["back_button_label"])
            actions.append({"id": "back", "label": back_label, "type": "back"})

        self.logger.log_view_rendered(user_id, screen_id, title)
        # Добавляем информацию о layout, если есть
        view_data = {"text": title, "actions": actions, "screen_type": screen_def["type"]}
        if screen_def.get("layout") == "grid":
            view_data["layout"] = "grid"
            view_data["columns"] = screen_def.get("columns", 1)
        return view_data

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        result = template
        for key, value in context.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    def _record_selection(self, user_id: str, screen_id: str, selected_item: Dict[str, Any]):
        """
        Записывает выбор пользователя.
        Если экран не поддерживает мультивыбор, удаляет предыдущие выборы на этом экране.
        """
        state = self.get_user_state(user_id)
        screen_def = self.manifest.screens.get(screen_id)
        supports_multi = screen_def.get("supports_multi_select", False)

        if not supports_multi:
            # Удаляем все предыдущие выборы на этом экране
            state["selections"] = [sel for sel in state["selections"] if sel.get("screen_id") != screen_id]

        # Добавляем новый выбор
        # Используем time.time() для timestamp
        state["selections"].append({
            "screen_id": screen_id,
            "selected_item": selected_item,
            "timestamp": time.time()
        })

    def _build_static_actions(self, screen_def: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions = []
        for i, btn in enumerate(screen_def["buttons"]):
            action_dict = {
                "id": f"static_{i}",
                "label": btn["label"],
            }
            # Проверяем, есть ли 'target' — если есть, то это навигация
            if "target" in btn:
                action_dict["type"] = "navigate"
                action_dict["target"] = btn["target"]
            # Если 'target' нет, но есть 'action' — это действие
            elif "action" in btn:
                action_dict["type"] = "action"
                action_dict["action"] = btn["action"]
            # Если нет ни 'target', ни 'action', ставим 'unknown' и логируем
            else:
                action_dict["type"] = "unknown"
                self.logger.log_error(f"Кнопка не имеет ни 'target', ни 'action': {btn}")

            # Добавляем payload, если он есть
            if "payload" in btn:
                action_dict["payload"] = btn["payload"]

            actions.append(action_dict)
        return actions

    def _build_dynamic_actions(self, user_id: str, screen_def: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = self._render_template(screen_def["data_source"]["url"], context)
        self.logger.log_api_call(url, screen_def["data_source"]["method"])
        items = self.api_client.call(url, screen_def["data_source"]["method"])
        actions = []
        template = screen_def["button_template"]
        for i, item in enumerate(items):
            next_context = {}
            for ctx_key, item_key in template.get("context_fields", {}).items():
                next_context[ctx_key] = item.get(item_key, "")
            actions.append({
                "id": f"dynamic_{i}",
                "label": item.get(template["label_field"], f"Item {i}"),
                "type": "navigate",
                "target": template["target_screen"],
                "context": next_context
            })
        return actions

    def _build_paginated_actions(self, user_id: str, screen_def: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        items = screen_def["items"]
        page_size = self.manifest.defaults["pagination"]["page_size"]
        pagination_state = self._user_states[user_id]["pagination"]
        screen_id_key = screen_def.get("id", "unknown")
        current_page = pagination_state.get(screen_id_key, 0)
        start = current_page * page_size
        end = start + page_size
        page_items = items[start:end]
        actions = []
        for i, item in enumerate(page_items):
            actions.append({
                "id": f"paginated_{start + i}",
                "label": str(item),
                "type": "navigate",
                "target": screen_def.get("target", "item_selected"),
                "payload": str(item)
            })

        if end < len(items):
            actions.append({
                "id": "next_page",
                "label": self.manifest.defaults["pagination"]["next_label"],
                "type": "paginate",
                "direction": "next",
                "screen_id": screen_id_key
            })
        if current_page > 0:
            actions.append({
                "id": "prev_page",
                "label": self.manifest.defaults["pagination"]["prev_label"],
                "type": "paginate",
                "direction": "prev",
                "screen_id": screen_id_key
            })
        return actions

    def handle_action(self, user_id: str, action_data: Dict[str, Any]) -> Union[Dict[str, Any], None]:
        state = self.get_user_state(user_id)
        action_type = action_data["type"]
        self.logger.log_user_action(user_id, "unknown", action_data["label"])
        if action_type == "back":
            self._handle_back(user_id, state)
        elif action_type == "navigate":
            # --- ИСПРАВЛЕНО ---
            # Сохраняем текущий экран *до* навигации
            current_screen_before_navigate = state["current_screen"]
            self._handle_navigate(user_id, state, action_data)
            # Записываем выбор на *предыдущем* экране
            if "target" in action_data:
                self._record_selection(user_id, current_screen_before_navigate, {"type": "navigate", "target": action_data["target"]})
        elif action_type == "paginate":
            self._handle_paginate(user_id, state, action_data)
        elif action_type == "action":
            # Обработка действий, например submit_mark
            if "action" in action_data:
                if action_data["action"] == "submit_mark":
                    self._submit_mark(user_id, state, action_data) # Логика возврата внутри
                    # Записываем выбор действия
                    current_screen_before_action = state["current_screen"] # <-- Сохраняем и для action
                    self._record_selection(user_id, current_screen_before_action, {"type": "action", "action": action_data["action"]})
                else:
                    self.logger.log_error(f"Неизвестное действие: {action_data['action']}")
            else:
                self.logger.log_error(f"Действие не имеет ключа 'action': {action_data}")
        else:
            self.logger.log_error(f"Неизвестный тип действия: {action_type}")

    def _handle_back(self, user_id: str, state: Dict[str, Any]):
        current_screen = state["current_screen"]
        screen_def = self.manifest.screens.get(current_screen)
        if not screen_def:
            state["current_screen"] = "main"
            return
        back_path = screen_def.get("back_path")
        if back_path == "CONTEXTUAL":
            if state["return_stack"]:
                state["current_screen"] = state["return_stack"].pop()
            else:
                state["current_screen"] = "main"
        elif back_path:
            state["current_screen"] = back_path
        else:
            state["current_screen"] = "main"

    def _handle_navigate(self, user_id: str, state: Dict[str, Any], action_data: Dict[str, Any]):
        target_screen = action_data["target"]
        if target_screen not in self.manifest.screens:
            self.logger.log_error(f"Целевой экран не найден: {target_screen}")
            return
        next_screen_def = self.manifest.screens.get(target_screen, {})
        if next_screen_def.get("back_path") == "CONTEXTUAL":
            state["return_stack"].append(state["current_screen"])
        state["current_screen"] = target_screen
        if "context" in action_data:
            state["context"].update(action_data["context"])

    def _handle_paginate(self, user_id: str, state: Dict[str, Any], action_data: Dict[str, Any]):
        screen_id = action_data["screen_id"]
        direction = action_data["direction"]
        pagination_state = state["pagination"]
        current_page = pagination_state.get(screen_id, 0)
        new_page = current_page + (1 if direction == "next" else -1)
        pagination_state[screen_id] = max(0, new_page)

    def _submit_mark(self, user_id: str, state: Dict[str, Any], action_data: Dict[str, Any]):
        # Логгируем API вызов
        self.logger.log_api_call("/api/marks", "POST")
        # Сохраняем важные данные контекста (например, student_id, student_name)
        # которые должны остаться при возврате к select_metric
        saved_context = {key: value for key, value in state["context"].items() if key in ["student_id", "student_name"]}
        # Устанавливаем экран на 'select_metric' (указан в back_path для confirm_mark)
        screen_def = self.manifest.screens.get(state["current_screen"]) # Текущий экран - confirm_mark
        back_path = screen_def.get("back_path") if screen_def else "main"
        if back_path == "select_metric": # Явно проверяем, куда возвращаться
            state["current_screen"] = "select_metric"
            # Восстанавливаем контекст студента
            state["context"].update(saved_context)
            # Очищаем return_stack, так как возврат не по нему
            state["return_stack"] = []
        else:
            # Если back_path не select_metric, возвращаемся по стеку или на main
            if state["return_stack"]:
                state["current_screen"] = state["return_stack"].pop()
            else:
                state["current_screen"] = "main"

    def handle_user_input(self, user_id: str, text: str):
        state = self.get_user_state(user_id)
        screen_id = state["current_screen"]
        screen_def = self.manifest.screens.get(screen_id)

        # Проверяем, находится ли пользователь в чат-режиме
        if screen_def and screen_def.get("type") == "chat_input":
            self.logger.log_user_action(user_id, "user_input", f"«{text}»")
            # Проверяем команды finish
            finish_commands = self.manifest.defaults["chat_mode"]["finish_commands"]
            if text.strip() in finish_commands:
                # Возвращаемся на back_path
                back_path = screen_def.get("back_path", "main")
                state["current_screen"] = back_path
                # Очищаем контекст чата, если есть
                # (например, если хранится история, её можно сбросить)
                # state["context"].pop("chat_history", None)
                return # Выход из обработки, обновление UI произойдёт в вызывающем коде

            # Имитация вызова AI
            # В реальности тут будет вызов API
            ai_response = f"Имитация ответа AI на: {text}"
            # В реальности, результат AI мог бы быть добавлен в контекст или отдельное поле
            # для отображения в GUI.
            # Например: state["context"]["last_ai_response"] = ai_response
            # Или, в GUI, это будет отображено как сообщение от бота.
            # Мы просто логгируем имитацию.
            self.logger.log_api_call("/api/ai/teacher-assist", "POST")
            self.logger.logger.info(f"USER[{user_id}] AI_RESPONSE: {ai_response}")

        else:
            # Если не в чат-режиме, можно игнорировать или логировать
            self.logger.log_user_action(user_id, "user_input_ignored", f"«{text}» - not in chat mode")
