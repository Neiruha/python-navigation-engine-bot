from textual.app import App, ComposeResult
from textual.widgets import Static, Button, Footer, Input
from textual.containers import Vertical, Horizontal
from .engine import NavigationEngine

class NavigationTextualApp(App):
    CSS = """
    Vertical {
        align: center middle;
    }
    #title {
        text-align: center;
        margin: 2 0;
        color: #0080FF; /* Светлый синий как пример 'акцента', можно изменить */
        text-style: bold;
    }
    /* Класс для чат-заголовка */
    #title.chat-mode {
        color: #CCCCCC; /* Серый как пример 'текста', можно изменить */
        text-style: italic;
    }
    Button {
        width: 40;
        margin: 1 0;
    }
    Horizontal { /* Для сетки */
        width: 90%; /* Не на всю ширину, чуть меньше для центровки */
        height: auto;
        align: center middle; /* Центруем контейнер Horiz внутри Vert */
    }
    Horizontal Button {
        width: 1fr; /* Кнопки делят ширину строки поровну */
        margin: 0 1; /* Отступы между кнопками */
    }
    #chat_input_widget {
        width: 80%;
        margin: 1 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.engine = NavigationEngine()
        self.user_id = "test-user"
        self.engine.init_user(self.user_id)
        # self._chat_widgets больше не нужен, так как используем buttons_container.remove_children()

    def compose(self) -> ComposeResult:
        yield Static("", id="title")
        yield Vertical(id="buttons_container")
        yield Footer()

    def update_ui(self):
        view = self.engine.get_current_view(self.user_id)
        title_widget = self.query_one("#title", Static)
        buttons_container = self.query_one("#buttons_container", Vertical)
        footer_widget = self.query_one(Footer)

        # Показываем или скрываем Footer в зависимости от режима
        if view.get("screen_type") == "chat_input":
            footer_widget.display = False
            title_widget.add_class("chat-mode")
        else:
            footer_widget.display = True
            title_widget.remove_class("chat-mode")

        title_widget.update(view["text"])

        # Удаляем *все* предыдущие элементы из контейнера кнопок
        buttons_container.remove_children()

        if view.get("screen_type") == "chat_input":
            # Режим чата
            # Убираем id у Input, чтобы избежать дублирования
            input_widget = Input(placeholder="Введите сообщение...", classes="chat_input_widget")
            buttons_container.mount(input_widget)
            # Фокус на ввод
            self.set_focus(input_widget)

        else:
            # Стандартный режим
            layout = view.get("layout")
            columns = view.get("columns", 1)

            if layout == "grid" and columns > 1:
                all_actions = view["actions"]
                back_action = None
                if all_actions and all_actions[-1].get("type") == "back":
                    back_action = all_actions.pop()

                rows = []
                for i in range(0, len(all_actions), columns):
                    row_actions = all_actions[i:i + columns]
                    rows.append(row_actions)

                for row_actions in rows:
                    row_container = Horizontal()
                    buttons_container.mount(row_container)
                    for action in row_actions:
                        btn = Button(action["label"])
                        btn.action_data = action
                        row_container.mount(btn)

                if back_action:
                    back_btn = Button(back_action["label"])
                    back_btn.action_data = back_action
                    buttons_container.mount(back_btn)

            else:
                for action in view["actions"]:
                    btn = Button(action["label"])
                    btn.action_data = action
                    buttons_container.mount(btn)

    def on_mount(self):
        self.update_ui()

    def on_button_pressed(self, event: Button.Pressed):
        action_data = event.button.action_data
        self.engine.handle_action(self.user_id, action_data)
        self.update_ui()

    def on_input_submitted(self, event: Input.Submitted):
        # Обработчик для *любого* Input в приложении, у которого был submitted
        # Так как у нас теперь только один Input, проблем не будет
        input_text = event.value
        # Очищаем поле ввода
        event.input.value = ""
        # Передаём текст в engine
        self.engine.handle_user_input(self.user_id, input_text)
        # Обновляем UI, чтобы отразить изменения (например, возврат из чата)
        self.update_ui()


if __name__ == "__main__":
    NavigationTextualApp().run()