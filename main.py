import enum
import json
import subprocess
import click
import core
from sys import exit


@click.command()
@click.option("--path", default="./config.json", help="Path to v2ray config.")
def main(path):
    try:
        is_gum_installed()
        config = core.Config()
        config.load()
        manager = core.ClientManager(config, path)
        manager.load()
        menu(manager)
    except FileNotFoundError as e:
        print(f"Config file not found: {e.filename}")
        exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Quitting...") # TODO: This is thrown whenever the user presses Ctrl+C in the middle of a command. Find a way to catch this.
        exit(1)
    except json.decoder.JSONDecodeError as e:
        print(f"Config file is not a valid JSON file: {e}")
        exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        exit(1)

class Menu(str, enum.Enum):
    LIST_CLIENTS = "List clients"
    ADD_CLIENT = "Add client"
    REMOVE_CLIENT = "Remove client"
    UTILS = "Utilities"
    QUIT = "Quit"

class EditMenu(str, enum.Enum):
    ASSIGN_NAME = "Assign name"
    CHANGE_LEVEL = "Change level"
    CHANGE_STARTDATE = "Change start date"
    EXTEND = "Extend"
    EXPIRE = "Expire"
    SHOW_INFO = "Show info"
    BACK = "Back"

class UtilityMenu(str, enum.Enum):
    LIST_EXPIRED = "List expired clients"
    CLEAR_EXPIRED = "Clear expired clients"
    RECALCULATE_ENDDATES = "Recalculate end dates"
    BACK = "Back"

def input(placeholder: str, prompt = "> ") -> str:
    return subprocess.check_output(["gum", "input",f"--placeholder={placeholder}", f"--prompt={prompt}"], text=True).strip() # type: ignore

def chooser_list(*items: str) -> str:
    return subprocess.check_output(["gum", "choose", *items], text=True).strip() # type: ignore

def confirm(prompt: str = "Are you sure?") -> bool:
    try:
        subprocess.check_output(["gum", "confirm", f"{prompt}"], text=True) # type: ignore
        return True
    except subprocess.CalledProcessError:
        return False

def duration_menu() -> float:
    chosen = chooser_list("1 day", "1 week", "1 month", "3 months")
    match chosen:
        case "1 day":
            return core.DURATION.ONE_DAY
        case "1 week":
            return core.DURATION.ONE_WEEK
        case "1 month":
            return core.DURATION.ONE_MONTH
        case "3 months":
            return core.DURATION.THREE_MONTHS
        case _:
            print("Invalid choice.")
            return duration_menu()

def edit_menu(manager: core.ClientManager, client: core.Client):
    chosen = chooser_list(*[item.value for item in EditMenu])
    match chosen:
        case EditMenu.ASSIGN_NAME.value:
            client.name = input("Enter the name of the client...")
        case EditMenu.CHANGE_LEVEL.value:
            client.level = int(input("Enter the level of the client..."))
        case EditMenu.CHANGE_STARTDATE.value:
            start_date = input("Enter the start date of the client...")
            client.start_date = core.parse_date(start_date)
        case EditMenu.EXTEND.value:
            client.extend(duration_menu())
        case EditMenu.EXPIRE.value:
            if confirm("Are you sure you want to expire this client?"):
                manager.stop_client(client)
        case EditMenu.SHOW_INFO.value:
            print(client.show())
        case EditMenu.BACK.value:
            menu(manager)
        case _:
            print("Invalid choice.")
    manager.update_client(client)
    menu(manager)

def add_menu(manager: core.ClientManager):
    chosen = chooser_list("Add client", "Add client with custom UUID", "Back")
    match chosen:
        case "Add client":
            name = input("Enter the name of the client...")
            level = int(input("Enter the level of the client..."))
            duration = duration_menu()
            client = core.Client(name, core.generate_uuid(), duration = duration, level=level)
            manager.add_client(client)
        case "Add client with custom UUID":
            name = input("Enter the name of the client...")
            level = int(input("Enter the level of the client..."))
            duration = duration_menu()
            uuid = input("Enter the UUID of the client...")
            if core.validate_uuid(uuid):
                client = core.Client(name, uuid, duration = duration, level=level)
                manager.add_client(client)
            else:
                print("Invalid UUID.")
                add_menu(manager)
        case "Back":
            menu(manager)

def utils_menu(manager: core.ClientManager):
    chosen = chooser_list(*[item.value for item in UtilityMenu]).strip()
    match chosen:
        case UtilityMenu.LIST_EXPIRED.value:
            expired = manager.list_expired()
            if expired:
                chooser_list(*[client.preview() for client in expired])
            else:
                print("No expired clients.")
        case UtilityMenu.CLEAR_EXPIRED.value:
            if confirm("Are you sure you want to clear all expired clients?"):
                print(f"Removed {len(manager.list_expired())} expired clients.")
                manager.clear_expired()
        case UtilityMenu.RECALCULATE_ENDDATES.value:
            if confirm("Are you sure you want to recalculate all end dates?"):
                manager.recalculate_end_dates()
        case UtilityMenu.BACK.value:
            menu(manager)
    menu(manager)

def menu(manager: core.ClientManager):
    chosen = chooser_list(*[item.value for item in Menu]).strip()
    match chosen:
        case Menu.LIST_CLIENTS.value:
            selected = chooser_list(*[client.preview() for client in manager._clients.values()]) # type: ignore
            selected = manager._clients[selected.split(" ")[0]]
            edit_menu(manager, selected)
        case Menu.ADD_CLIENT.value:
            add_menu(manager)
        case Menu.REMOVE_CLIENT.value:
            selected = chooser_list(*[client.preview() for client in manager._clients.values()]) # type: ignore
            selected = manager._clients[selected.split(" ")[0]]
            if confirm("Are you sure you want to remove this client?"):
                manager.stop_client(selected)
            else:
                menu(manager)
        case Menu.UTILS.value:
            utils_menu(manager)
        case Menu.QUIT.value:
            exit(0)
        case _:
            print("Invalid choice.")

def is_gum_installed():
    from shutil import which
    if which("gum") is None:
        raise subprocess.CalledProcessError(1, "gum")


if __name__ == "__main__":
    main()
