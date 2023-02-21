import json
import os
import time
from config import Config

ONEMONTH = 2592000

def time_to_string(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))

class Client:
    def __init__(self, name: str, id: str, start_date: float, duration: float = ONEMONTH, level: int = 1) -> None:
        self.name = name
        self.id = id
        self.level = level
        self.start_date = start_date
        self.duration = duration
        self.end_date = start_date + duration
        self.is_expired = time.time() > self.end_date

    def __str__(self) -> str:
        return f"Client(name={self.name}, id={self.id}, start_date={time_to_string(self.start_date)}, end_date={time_to_string(self.end_date)})"

    def update_expiration(self) -> None:
        self.is_expired = time.time() > self.end_date

    def extend(self, duration: float = ONEMONTH) -> None:
        self.start_date += duration
        self.end_date = self.start_date + self.duration
        self.is_expired = time.time() > self.end_date

    def encode(self) -> dict[str, str | float]:
        return {
            "name": self.name,
            "id": self.id,
            "level": self.level,
            "start_date": self.start_date,
            "duration": self.duration,
            "end_date": self.end_date,
            "is_expired": self.is_expired
        }

class ClientManager:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._path = self._config.path()
        self._clients: dict[str, Client] = {}
        self._v2ray_clients: list[str] = []

    def load_v2ray(self, path: str) -> None:
        with open(path, "r") as f:
            data = json.load(f)
        for client in data["inbounds"][0]["settings"]["clients"]:
            self._v2ray_clients.append(client["id"])

    def load(self) -> None:
        if not os.path.exists(self._path):
            os.makedirs(self._path)
        if not os.path.exists(os.path.join(self._path, "clients.json")):
            self.save()
        with open(os.path.join(self._path, "clients.json"), "r") as f:
            self._clients = json.load(f)

    def save(self) -> None:
        with open(os.path.join(self._path, "clients.json"), "w") as f:
            json.dump(self._clients,default=lambda o: o.encode(), indent=4, sort_keys=True, fp=f)

    def get(self, key: str) -> Client | None:
        return self._clients.get(key)

    def set(self, key: str, value: Client) -> None:
        self._clients[key] = value
