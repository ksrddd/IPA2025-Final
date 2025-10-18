import os
import json
import requests
from dotenv import load_dotenv
load_dotenv()
requests.packages.urllib3.disable_warnings()

# ====== ENV / CONFIG ======
ROUTER_IP   = os.environ.get("ROUTER_IP", "10.0.15.63").strip()
STUDENT_ID  = os.environ.get("STUDENT_ID", "66070315").strip()
RESTCONF_PORT = os.environ.get("RESTCONF_PORT", "443").strip()

# ชื่อที่ใช้ "คอนฟิกจริง" (ไม่มีเว้นวรรค, L ใหญ่)
IF_NAME_CFG = f"Loopback{STUDENT_ID}"
# ชื่อที่ใช้ "ในข้อความ" (ตัวเล็ก + เว้นวรรค) ให้ตรงสเปกข้อความ
IF_NAME_MSG = f"loopback {STUDENT_ID}"

def ip_for_student(student_id: str) -> str:
    last3 = student_id[-3:]
    x = int(last3[0])
    y = int(last3[1:])
    return f"172.{x}.{y}.1"

LOOPBACK_IP = ip_for_student(STUDENT_ID)

BASE = f"https://{ROUTER_IP}:{RESTCONF_PORT}/restconf/data"
CFG_ROOT = f"{BASE}/ietf-interfaces:interfaces"
STATE_ROOT = f"{BASE}/ietf-interfaces:interfaces-state"

headers = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}
basicauth = ("admin", "cisco")

# ---------- helpers ----------
def has_interface() -> bool:
    url = f"{CFG_ROOT}/interface={IF_NAME_CFG}"
    r = requests.get(url, auth=basicauth, headers=headers, verify=False)
    return r.status_code == 200

# ---------- CRUD ----------
def create():
    payload_full = {
        "ietf-interfaces:interface": {
            "name": IF_NAME_CFG,
            "description": f"Student {STUDENT_ID} loopback",
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
            "ietf-ip:ipv4": {"address": [{"ip": LOOPBACK_IP, "netmask": "255.255.255.0"}]},
        }
    }
    # ลอง POST ไป collection ก่อน
    r = requests.post(CFG_ROOT, data=json.dumps(payload_full),
                      auth=basicauth, headers=headers, verify=False)
    if r.status_code in (200, 201, 204):
        return f"Interface {IF_NAME_MSG} is created successfully"
    if r.status_code == 409:
        return f"Cannot create: Interface {IF_NAME_MSG}"
    # fallback PUT (บาง image ต้องใช้)
    r2 = requests.put(f"{CFG_ROOT}/interface={IF_NAME_CFG}",
                      data=json.dumps(payload_full["ietf-interfaces:interface"]),
                      auth=basicauth, headers=headers, verify=False)
    if r2.status_code in (200, 201, 204):
        return f"Interface {IF_NAME_MSG} is created successfully"
    if r2.status_code == 409:
        return f"Cannot create: Interface {IF_NAME_MSG}"
    print(f"Create error: {r.status_code} {r.text} / {r2.status_code} {r2.text}")
    return f"Cannot create: Interface {IF_NAME_MSG}"

def delete():
    r = requests.delete(f"{CFG_ROOT}/interface={IF_NAME_CFG}",
                        auth=basicauth, headers=headers, verify=False)
    if r.status_code in (200, 204):
        return f"Interface {IF_NAME_MSG} is deleted successfully"
    if r.status_code == 404:
        return f"Cannot delete: Interface {IF_NAME_MSG}"
    print(f"Delete error: {r.status_code} {r.text}")
    return f"Cannot delete: Interface {IF_NAME_MSG}"

def enable():
    payload = {
        "ietf-interfaces:interface": {
            "name": IF_NAME_CFG,
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
        }
    }
    r = requests.patch(f"{CFG_ROOT}/interface={IF_NAME_CFG}",
                       data=json.dumps(payload), auth=basicauth,
                       headers=headers, verify=False)
    if r.status_code in (200, 204):
        return f"Interface {IF_NAME_MSG} is enabled successfully"
    if r.status_code == 404:
        return f"Cannot enable: Interface {IF_NAME_MSG}"
    print(f"Enable error: {r.status_code} {r.text}")
    return f"Cannot enable: Interface {IF_NAME_MSG}"

def disable():
    payload = {
        "ietf-interfaces:interface": {
            "name": IF_NAME_CFG,
            "type": "iana-if-type:softwareLoopback",
            "enabled": False,
        }
    }
    r = requests.patch(f"{CFG_ROOT}/interface={IF_NAME_CFG}",
                       data=json.dumps(payload), auth=basicauth,
                       headers=headers, verify=False)
    if r.status_code in (200, 204):
        return f"Interface {IF_NAME_MSG} is shutdowned successfully"
    if r.status_code == 404:
        return f"Cannot shutdown: Interface {IF_NAME_MSG}"
    print(f"Disable error: {r.status_code} {r.text}")
    return f"Cannot shutdown: Interface {IF_NAME_MSG}"

def status():
    # อ่าน enabled จาก config
    r_cfg = requests.get(f"{CFG_ROOT}/interface={IF_NAME_CFG}",
                         auth=basicauth, headers=headers, verify=False)
    if r_cfg.status_code == 404:
        return f"No Interface {IF_NAME_MSG}"
    if r_cfg.status_code not in (200,):
        print(f"Status cfg error: {r_cfg.status_code} {r_cfg.text}")
        return f"No Interface {IF_NAME_MSG}"
    enabled = bool(r_cfg.json().get("ietf-interfaces:interface", {}).get("enabled", False))

    # อ่าน oper-status จาก state
    r_state = requests.get(f"{STATE_ROOT}/interface={IF_NAME_CFG}",
                           auth=basicauth, headers=headers, verify=False)
    oper = "unknown"
    if r_state.status_code == 200:
        oper = r_state.json().get("ietf-interfaces:interface", {}).get("oper-status", "unknown")

    if enabled and oper == "up":
        return f"Interface {IF_NAME_MSG} is enabled"
    if not enabled:
        return f"Interface {IF_NAME_MSG} is disabled"
    return f"Interface {IF_NAME_MSG} admin={'up' if enabled else 'down'}, oper={oper}"

def handle_command(cmd: str) -> str:
    cmd = (cmd or "").strip().lower()
    try:
        if cmd == "create":
            if has_interface():
                return f"Cannot create: Interface {IF_NAME_MSG}"
            return create()
        elif cmd == "delete":
            if not has_interface():
                return f"Cannot delete: Interface {IF_NAME_MSG}"
            return delete()
        elif cmd == "enable":
            if not has_interface():
                return f"Cannot enable: Interface {IF_NAME_MSG}"
            return enable()
        elif cmd == "disable":
            if not has_interface():
                return f"Cannot shutdown: Interface {IF_NAME_MSG}"
            return disable()
        elif cmd == "status":
            return status()
        else:
            return "Unknown command"
    except Exception as e:
        print(f"Exception in handle_command: {e}")
        if cmd == "create":  return f"Cannot create: Interface {IF_NAME_MSG}"
        if cmd == "delete":  return f"Cannot delete: Interface {IF_NAME_MSG}"
        if cmd == "enable":  return f"Cannot enable: Interface {IF_NAME_MSG}"
        if cmd == "disable": return f"Cannot shutdown: Interface {IF_NAME_MSG}"
        if cmd == "status":  return f"No Interface {IF_NAME_MSG}"
        return "Unknown command"
