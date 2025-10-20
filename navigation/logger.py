import logging
from typing import Optional

class NavigationLogger:
    def __init__(self, name: str = "NavigationEngine", level: int = logging.INFO, log_file: str = "navigation.log"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        if not self.logger.handlers:
            formatter = logging.Formatter(
                "[%(asctime)s] %(name)s :: %(levelname)s :: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            # Только файл — без консоли
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def log_view_rendered(self, user_id: str, screen_id: str, text: str):
        self.logger.info(f"USER[{user_id}] VIEW[{screen_id}]: {text[:60]}...")

    def log_user_action(self, user_id: str, action_id: str, label: str):
        self.logger.info(f"USER[{user_id}] ACTION: '{label}' (id={action_id})")

    def log_api_call(self, url: str, method: str):
        self.logger.debug(f"API CALL: {method} {url}")

    def log_error(self, message: str):
        self.logger.error(message)