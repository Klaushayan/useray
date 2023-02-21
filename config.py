import json
import os

APP_NAME = "useray"
APP_VERSION = "0.1"


def os_name():
    import platform
    return platform.system()

def config_dir():
    match os_name():
        case "Windows":
            return os.path.join(os.environ["APPDATA"], APP_NAME)
        case "Linux" | "Darwin":
            return os.path.join(os.environ["HOME"], ".config", APP_NAME)
        case _:  # default
            raise Exception("Unsupported OS")

class Config:
    def __init__(self, config_dir = config_dir()):
        self._config_dir = config_dir
        self._config_path = os.path.join(self._config_dir, "config.json")
        self._config = {}

    def load(self):
        if os.path.exists(self._config_path):
            with open(self._config_path, "r") as f:
                self._config = json.load(f)

    def save(self):
        if not os.path.exists(self._config_dir):
            os.makedirs(self._config_dir)
        with open(self._config_path, "w") as f:
            json.dump(self._config, f, indent=4)

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value

    def path(self):
        return self._config_dir