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
    for key, value in data.items():
        end_date = value.pop("end_date", None)
        is_expired = value.pop("is_expired", None)
        data[key] = Client(**value)
        if end_date is not None:
            data[key].end_date = end_date
        if is_expired is not None:
            data[key].is_expired = is_expired
    return data

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
        self.duration += duration
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

    def days_left(self) -> int:
        return int((self.end_date - time.time()) / DURATION.ONE_DAY)

    def preview(self) -> str:
        return f"{self.id} ({self.name})"

    # show client info with human readable format, expiring date, duration, days left etc.
    def show(self) -> str:
        return f"""Client Info:
    Name: {self.name}
    ID: {self.id}
    Level: {self.level}
    Start Date: {time_to_string(self.start_date)}
    End Date: {time_to_string(self.end_date)}
    Duration: {self.duration / DURATION.ONE_DAY} Days
    Days Left: {self.days_left()}
    Expired: {self.is_expired}
    """

class ClientManager:
    def __init__(self, config: Config, v2ray_path: str) -> None:
        self._config = config
        self._path = self._config.path()
        self._clients: dict[str, Client] = {}
        self._v2ray_list = V2rayList(v2ray_path).verify_path().load()
        self.load()
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
        print(f"Adding {client.name} with UUID {client.id}...")
        self.save()

    def extend_client(self, client: Client) -> None:
        self._clients[client.id].extend()
        self.save()

    def stop_client(self, client: Client) -> None:
        self._clients[client.id].stop()
        self._v2ray_list.expire(client)
        self.save()

    def update_client(self, client: Client) -> None:
        self._clients[client.id] = client
        self.save()

    def list_expired(self) -> list[Client]:
        return [client for client in self._clients.values() if client.update_expiration().is_expired]

    def clear_expired(self) -> None:
        for client in self.list_expired():
            self._v2ray_list.expire(client)
            del self._clients[client.id]
        self.save()

    def _sync(self) -> None:
        for client in self._v2ray_list:
            if client not in self._clients:
                self._clients[client] = Client("No name", client, time.time(), DURATION.ONE_MONTH)
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
        self._clients: list[str] = [] # this is usually str, TODO: fix the type hinting later

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
            self._clients.append(client.id)
            with open(self._path, "r") as f:
                data = json.load(f)
            with open(self._path, "w") as f:
                data["inbounds"][0]["settings"]["clients"].append(
                    {"id": client.id, "level": client.level, "alterId": 0}
                )
                json.dump(data, f, indent=4)
        return self

    def expire(self, client: Client) -> V2rayList:
        if not client.update_expiration().is_expired:
            raise ValueError("Client is not expired")
        if client.id in self._clients:
            self._clients.remove(client.id)
            with open(self._path, "r") as f:
                data = json.load(f)
            with open(self._path, "w") as f:
                for i, c in enumerate(data["inbounds"][0]["settings"]["clients"]):
                    if c["id"] == client.id:
                        del data["inbounds"][0]["settings"]["clients"][i]
                        break
                json.dump(data, f, indent=4)
        return self

    def __iter__(self) -> Iterator[str]:
        return iter(self._clients)

    def __len__(self) -> int:
        return len(self._clients)

    def __getitem__(self, key: int) -> str:
        return self._clients[key]

    def __setitem__(self, key: int, value: Client) -> None:
        self._clients[key] = value.id

    def __delitem__(self, key: int) -> None:
        del self._clients[key]

    def __contains__(self, item: str) -> bool:
        return item in self._clients