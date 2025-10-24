# restconf_final.py
import os
import time
import json
import requests
from dotenv import load_dotenv
load_dotenv()
requests.packages.urllib3.disable_warnings()

STUDENT_ID    = os.environ.get("STUDENT_ID", "66070315").strip()
RESTCONF_PORT = os.environ.get("RESTCONF_PORT", "443").strip()

TIMEOUT = float(os.environ.get("RESTCONF_TIMEOUT", 8))
RETRIES = int(os.environ.get("RESTCONF_RETRIES", 3))
BACKOFF = float(os.environ.get("RESTCONF_BACKOFF", 1.5))

IF_NAME_CFG = f"Loopback{STUDENT_ID}"
IF_NAME_MSG = f"loopback {STUDENT_ID}"

def ip_for_student(student_id: str) -> str:
    last3 = student_id[-3:]
    x = int(last3[0])
    y = int(last3[1:])
    return f"172.{x}.{y}.1"

LOOPBACK_IP = ip_for_student(STUDENT_ID)

def _base(router_ip: str) -> tuple[str, str]:
    base = f"https://{router_ip}:{RESTCONF_PORT}/restconf/data"
    return (f"{base}/ietf-interfaces:interfaces",
            f"{base}/ietf-interfaces:interfaces-state")

headers = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}
basicauth = (os.environ.get("ROUTER_USER", "admin"),
             os.environ.get("ROUTER_PASS", "cisco"))

def _request(method: str, url: str, **kwargs) -> requests.Response:
    kwargs.setdefault("auth", basicauth)
    kwargs.setdefault("headers", headers)
    kwargs.setdefault("verify", False)
    kwargs.setdefault("timeout", TIMEOUT)
    last_exc = None
    delay = 0
    for _ in range(RETRIES):
        if delay:
            time.sleep(delay)
        try:
            return requests.request(method.upper(), url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_exc = e
            delay = delay * BACKOFF if delay else BACKOFF
    raise last_exc if last_exc else RuntimeError("Unknown request error")

def has_interface(router_ip: str) -> bool:
    CFG_ROOT, _ = _base(router_ip)
    r = _request("GET", f"{CFG_ROOT}/interface={IF_NAME_CFG}")
    return r.status_code == 200

def create(router_ip: str) -> str:
    CFG_ROOT, _ = _base(router_ip)
    payload = {
        "ietf-interfaces:interface": {
            "name": IF_NAME_CFG,
            "description": f"Student {STUDENT_ID} loopback",
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
            "ietf-ip:ipv4": {"address": [{"ip": LOOPBACK_IP, "netmask": "255.255.255.0"}]},
        }
    }
    r = _request("POST", CFG_ROOT, data=json.dumps(payload))
    if r.status_code in (200, 201, 204):
        return f"Interface {IF_NAME_MSG} is created successfully"
    if r.status_code == 409:
        return f"Cannot create: Interface {IF_NAME_MSG}"
    # fallback PUT
    r2 = _request("PUT", f"{CFG_ROOT}/interface={IF_NAME_CFG}",
                  data=json.dumps(payload["ietf-interfaces:interface"]))
    if r2.status_code in (200, 201, 204):
        return f"Interface {IF_NAME_MSG} is created successfully"
    if r2.status_code == 409:
        return f"Cannot create: Interface {IF_NAME_MSG}"
    return f"Cannot create: Interface {IF_NAME_MSG}"

def delete(router_ip: str) -> str:
    CFG_ROOT, _ = _base(router_ip)
    r = _request("DELETE", f"{CFG_ROOT}/interface={IF_NAME_CFG}")
    if r.status_code in (200, 204):
        return f"Interface {IF_NAME_MSG} is deleted successfully"
    if r.status_code == 404:
        return f"Cannot delete: Interface {IF_NAME_MSG}"
    return f"Cannot delete: Interface {IF_NAME_MSG}"

def enable(router_ip: str) -> str:
    CFG_ROOT, _ = _base(router_ip)
    payload = {"ietf-interfaces:interface": {"name": IF_NAME_CFG,
                "type": "iana-if-type:softwareLoopback", "enabled": True}}
    r = _request("PATCH", f"{CFG_ROOT}/interface={IF_NAME_CFG}", data=json.dumps(payload))
    if r.status_code in (200, 204):
        return f"Interface {IF_NAME_MSG} is enabled successfully"
    if r.status_code == 404:
        return f"Cannot enable: Interface {IF_NAME_MSG}"
    return f"Cannot enable: Interface {IF_NAME_MSG}"

def disable(router_ip: str) -> str:
    CFG_ROOT, _ = _base(router_ip)
    payload = {"ietf-interfaces:interface": {"name": IF_NAME_CFG,
                "type": "iana-if-type:softwareLoopback", "enabled": False}}
    r = _request("PATCH", f"{CFG_ROOT}/interface={IF_NAME_CFG}", data=json.dumps(payload))
    if r.status_code in (200, 204):
        return f"Interface {IF_NAME_MSG} is shutdowned successfully"
    if r.status_code == 404:
        return f"Cannot shutdown: Interface {IF_NAME_MSG}"
    return f"Cannot shutdown: Interface {IF_NAME_MSG}"

def status(router_ip: str) -> str:
    CFG_ROOT, STATE_ROOT = _base(router_ip)
    r_cfg = _request("GET", f"{CFG_ROOT}/interface={IF_NAME_CFG}")
    if r_cfg.status_code == 404:
        return f"No Interface {IF_NAME_MSG}"
    if r_cfg.status_code != 200:
        return f"No Interface {IF_NAME_MSG}"
    enabled = bool(r_cfg.json().get("ietf-interfaces:interface", {}).get("enabled", False))

    r_state = _request("GET", f"{STATE_ROOT}/interface={IF_NAME_CFG}")
    oper = "unknown"
    if r_state.status_code == 200:
        oper = r_state.json().get("ietf-interfaces:interface", {}).get("oper-status", "unknown")

    if enabled and oper == "up":
        return f"Interface {IF_NAME_MSG} is enabled"
    if not enabled:
        return f"Interface {IF_NAME_MSG} is disabled"
    return f"Interface {IF_NAME_MSG} admin={'up' if enabled else 'down'}, oper={oper}"

def handle_command(cmd: str, router_ip: str) -> str:
    try:
        if cmd == "create":
            return create(router_ip) if not has_interface(router_ip) else f"Cannot create: Interface {IF_NAME_MSG}"
        if cmd == "delete":
            return delete(router_ip) if has_interface(router_ip) else f"Cannot delete: Interface {IF_NAME_MSG}"
        if cmd == "enable":
            return enable(router_ip) if has_interface(router_ip) else f"Cannot enable: Interface {IF_NAME_MSG}"
        if cmd == "disable":
            return disable(router_ip) if has_interface(router_ip) else f"Cannot shutdown: Interface {IF_NAME_MSG}"
        if cmd == "status":
            return status(router_ip)
        return "Unknown command"
    except Exception:
        if cmd == "create":  return f"Cannot create: Interface {IF_NAME_MSG}"
        if cmd == "delete":  return f"Cannot delete: Interface {IF_NAME_MSG}"
        if cmd == "enable":  return f"Cannot enable: Interface {IF_NAME_MSG}"
        if cmd == "disable": return f"Cannot shutdown: Interface {IF_NAME_MSG}"
        if cmd == "status":  return f"No Interface {IF_NAME_MSG}"
        return "Unknown command"
