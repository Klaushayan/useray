from __future__ import annotations
import json
import os
import time
from typing import Iterator
from config import Config


class DURATION:
    ONE_DAY = 86400
    ONE_WEEK = 604800
    ONE_MONTH = 2592000
    THREE_MONTHS = 7776000


def time_to_string(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))

def json_to_client(data: dict) -> dict[str, Client]:
    # remove end_date and is_expired
    for key, value in data.items():
        value.pop("end_date", None)
        value.pop("is_expired", None)
    return {key: Client(**value) for key, value in data.items()}

def generate_uuid() -> str:
    import uuid
    return str(uuid.uuid1())

def validate_uuid(uuid: str) -> bool:
    import re
    return bool(re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", uuid, re.I))

def parse_date(date: str) -> float:
    import datetime
    return datetime.datetime.strptime(date, "%Y-%m-%d").timestamp()

class Client:
    def __init__(
        self,
        name: str,
        id: str,
        start_date: float = time.time(),
        duration: float = DURATION.ONE_MONTH,
        level: int = 1,
    ) -> None:
        self.name = name
        self.id = id
        self.level = level
        self.start_date = start_date
        self.duration = duration
        self.end_date = start_date + duration
        self.is_expired = time.time() > self.end_date

    def __str__(self) -> str:
        return f"Client(name={self.name}, id={self.id}, start_date={time_to_string(self.start_date)}, end_date={time_to_string(self.end_date)})"

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, other: Client) -> bool:
        return self.id == other.id

    def __iter__(self) -> Iterator[Client]:
        yield self

    def update_expiration(self) -> Client:
        self.is_expired = time.time() > self.end_date
        return self

    def extend(self, duration: float = DURATION.ONE_MONTH) -> Client:
        self.start_date += duration
        self.end_date = self.start_date + self.duration
        self.is_expired = time.time() > self.end_date
        return self

    def stop(self) -> Client:
        self.end_date = time.time() - 1
        self.update_expiration()
        return self

    def resume(self) -> Client:
        self.end_date = self.start_date + self.duration
        self.update_expiration()
        return self

    def encode(self) -> dict[str, str | float]:
        return self.__dict__

    def preview(self) -> str:
        return f"{self.id} ({self.name})"


class ClientManager:
    def __init__(self, config: Config, v2ray_path: str) -> None:
        self._config = config
        self._path = self._config.path()
        self._clients: dict[str, Client] = {}
        self._v2ray_list = V2rayList(v2ray_path).verify_path().load()
        self._sync()

    def load(self) -> None:
        if not os.path.exists(self._path):
            os.makedirs(self._path)
        if not os.path.exists(os.path.join(self._path, "clients.json")):
            self.save()
        with open(os.path.join(self._path, "clients.json"), "r") as f:
            self._clients = json_to_client(json.load(f))

    def save(self) -> None:
        with open(os.path.join(self._path, "clients.json"), "w") as f:
            json.dump(
                self._clients,
                default=lambda o: o.encode(),
                indent=4,
                sort_keys=True,
                fp=f,
            )
    def add_client(self, client: Client) -> None:
        self._clients[client.id] = client
        self._v2ray_list.add(client)
        self.save()

    def extend_client(self, client: Client) -> None:
        self._clients[client.id].extend()
        self.save()

    def stop_client(self, client: Client) -> None:
        self._clients[client.id].stop()
        self._v2ray_list.expire(client)
        self.save()

    def _sync(self) -> None:
        for client in self._v2ray_list:
            if client not in self._clients:
                if type(client) is str:
                    self._clients[client] = Client("No name", client, time.time(), DURATION.ONE_MONTH)
                else:
                    self._clients[client.id] = client
        for client in self._clients.values():
            client.update_expiration()
            if client.is_expired:
                self._v2ray_list.expire(client)
        self.save()

    def get(self, key: str) -> Client | None:
        return self._clients.get(key)

    def set(self, key: str, value: Client) -> None:
        self._clients[key] = value


class V2rayList:
    def __init__(self, path: str = "./config.json") -> None:
        self._path = path
        self._clients: list[Client] = [] # this is usually str, TODO: fix the type hinting later

        self.verify_path()
        self.load()

    def verify_path(self) -> V2rayList:
        if not os.path.exists(self._path):
            raise FileNotFoundError("config.json not found")
        return self

    def load(self) -> V2rayList:
        self._clients.clear()
        with open(self._path, "r") as f:
            data = json.load(f)
        for client in data["inbounds"][0]["settings"]["clients"]:
            self._clients.append(client["id"])
        return self

    def add(self, client: Client) -> V2rayList:
        if client.id not in self._clients:
            self._clients.append(client)
            with open(self._path, "rw") as f:
                data = json.load(f)
                data["inbounds"][0]["settings"]["clients"].append(
                    {"id": client.id, "level": client.level, "alterId": 0}
                )
                json.dump(data, f, indent=4)
        return self

    def expire(self, client: Client) -> V2rayList:
        if not client.update_expiration().is_expired:
            raise ValueError("Client is not expired")
        if client.id in self._clients:
            self._clients.remove(client)
            with open(self._path, "rw") as f:
                data = json.load(f)
                for i, c in enumerate(data["inbounds"][0]["settings"]["clients"]):
                    if c["id"] == client.id:
                        del data["inbounds"][0]["settings"]["clients"][i]
                        break
                json.dump(data, f, indent=4)
        return self

    def __iter__(self) -> Iterator[Client]:
        return iter(self._clients)

    def __len__(self) -> int:
        return len(self._clients)

    def __getitem__(self, key: int) -> Client:
        return self._clients[key]

    def __setitem__(self, key: int, value: Client) -> None:
        self._clients[key] = value

    def __delitem__(self, key: int) -> None:
        del self._clients[key]

    def __contains__(self, item: Client | str) -> bool:
        if isinstance(item, Client):
            return item in self._clients
        else:
            for client in self._clients:
                if client.id == item:
                    return True
            return False