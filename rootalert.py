#!/usr/bin/env python3
import time
import re
import yaml
import requests
from pathlib import Path

CONFIG_PATH = "config.yaml"


def load_config(path: str):
    with open(path, "r") as f:
        return yaml.safe_load(f)


def send_telegram(bot_token: str, chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")


def follow(file_path: Path):
    with file_path.open("r") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            yield line


def parse_event(line: str):
    """
    Événements intéressants dans /var/log/secure (Rocky/RHEL) :
    - SSH login OK
    - SSH login FAILED
    - sudo → root OK
    - sudo FAILED
    """

    ssh_fail = re.search(
        r"Failed password for (invalid user )?(?P<user>\w+) from (?P<ip>[0-9.]+)",
        line,
    )
    if ssh_fail:
        return {
            "type": "ssh_failed",
            "user": ssh_fail.group("user"),
            "ip": ssh_fail.group("ip"),
            "raw": line.strip(),
        }

    ssh_ok = re.search(
        r"Accepted .* for (?P<user>\w+) from (?P<ip>[0-9.]+)",
        line,
    )
    if ssh_ok:
        return {
            "type": "ssh_login",
            "user": ssh_ok.group("user"),
            "ip": ssh_ok.group("ip"),
            "raw": line.strip(),
        }

    sudo_ok = re.search(
        r"sudo:\s*(?P<user>\w+)\s*:.*USER=root",
        line,
    )
    if sudo_ok:
        return {
            "type": "sudo_root",
            "user": sudo_ok.group("user"),
            "ip": "local",
            "raw": line.strip(),
        }

    sudo_fail = re.search(
        r"sudo:\s*(?P<user>\w+)\s*:.*(incorrect password attempts|authentication failure)",
        line,
    )
    if sudo_fail:
        return {
            "type": "sudo_failed",
            "user": sudo_fail.group("user"),
            "ip": "local",
            "raw": line.strip(),
        }

    return None


def is_trusted(event: dict, trusted_users, trusted_ips):
    # All FAILED suspects → jamais trusted
    if event["type"] in ("ssh_failed", "sudo_failed"):
        return False

    #succès, whitelist 
    if event["user"] in trusted_users:
        if event["ip"] in trusted_ips or event["ip"] == "local":
            return True
    return False


def main():
    config = load_config(CONFIG_PATH)
    bot_token = config["telegram"]["bot_token"]
    chat_id = config["telegram"]["chat_id"]
    log_path = Path(config["log"]["path"])

    trusted_users = set(config["trusted"]["users"])
    trusted_ips = set(config["trusted"]["ips"])

    print(f"[RootAlert] Monitoring {log_path}")

    for line in follow(log_path):
        event = parse_event(line)
        if not event:
            continue

        if is_trusted(event, trusted_users, trusted_ips):
            continue

        msg = (
            f"⚠️ RootAlert : Event detected\n"
            f"Type : {event['type']}\n"
            f"User : {event['user']}\n"
            f"IP   : {event['ip']}\n"
            f"Raw  : {event['raw']}"
        )

        print(msg)
        send_telegram(bot_token, chat_id, msg)


if __name__ == "__main__":
    main()
