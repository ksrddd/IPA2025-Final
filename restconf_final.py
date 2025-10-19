import os 
import time
import json
import requests
from dotenv import load_dotenv
load_dotenv()
requests.packages.urllib3.disable_warnings()

# ====== ENV / CONFIG ======
ROUTER_IP     = os.environ.get("ROUTER_IP", "10.0.15.63").strip()
STUDENT_ID    = os.environ.get("STUDENT_ID", "66070315").strip()
RESTCONF_PORT = os.environ.get("RESTCONF_PORT", "443").strip()

# Retry/Timeout settings (ตามรีเควส: ลองใหม่ 3 ครั้ง)
TIMEOUT = float(os.environ.get("RESTCONF_TIMEOUT", 8))   # วินาทีต่อครั้ง
RETRIES = int(os.environ.get("RESTCONF_RETRIES", 3))     # จำนวนครั้งรวม
BACKOFF = float(os.environ.get("RESTCONF_BACKOFF", 1.5)) # คูณเวลาหน่วงเมื่อพลาด

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

BASE       = f"https://{ROUTER_IP}:{RESTCONF_PORT}/restconf/data"
CFG_ROOT   = f"{BASE}/ietf-interfaces:interfaces"
STATE_ROOT = f"{BASE}/ietf-interfaces:interfaces-state"

headers = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}
basicauth = ("admin", "cisco")

# ---------- Retry helper ----------
def _request(method: str, url: str, **kwargs) -> requests.Response:
    """
    หุ้ม requests ด้วย retry (RETRIES ครั้ง) + timeout และ backoff
    โยน exception ออกไปถ้าล้มเหลวครบทุกครั้ง (ให้ handle_command จัดการข้อความ)
    """
    kwargs.setdefault("auth", basicauth)
    kwargs.setdefault("headers", headers)
    kwargs.setdefault("verify", False)
    kwargs.setdefault("timeout", TIMEOUT)

    last_exc = None
    delay = 0
    for attempt in range(1, RETRIES + 1):
        if delay:
            time.sleep(delay)
        try:
            return requests.request(method.upper(), url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_exc = e
            # หน่วงก่อนลองใหม่
            delay = delay * BACKOFF if delay else BACKOFF
    # หมดสิทธิ์ retry → โยนเอ็กซ์เซปชันให้คนเรียกตัดสินใจ
    raise last_exc if last_exc else RuntimeError("Unknown request error")

# ---------- helpers ----------
def has_interface() -> bool:
    url = f"{CFG_ROOT}/interface={IF_NAME_CFG}"
    r = _request("GET", url)
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
    # POST เข้า collection
    r = _request("POST", CFG_ROOT, data=json.dumps(payload_full))
    if r.status_code in (200, 201, 204):
        return f"Interface {IF_NAME_MSG} is created successfully"
    if r.status_code == 409:
        return f"Cannot create: Interface {IF_NAME_MSG}"
    # fallback PUT
    r2 = _request(
        "PUT",
        f"{CFG_ROOT}/interface={IF_NAME_CFG}",
        data=json.dumps(payload_full["ietf-interfaces:interface"]),
    )
    if r2.status_code in (200, 201, 204):
        return f"Interface {IF_NAME_MSG} is created successfully"
    if r2.status_code == 409:
        return f"Cannot create: Interface {IF_NAME_MSG}"
    print(f"Create error: {r.status_code} {r.text} / {r2.status_code} {r2.text}")
    return f"Cannot create: Interface {IF_NAME_MSG}"

def delete():
    r = _request("DELETE", f"{CFG_ROOT}/interface={IF_NAME_CFG}")
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
    r = _request("PATCH", f"{CFG_ROOT}/interface={IF_NAME_CFG}", data=json.dumps(payload))
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
    r = _request("PATCH", f"{CFG_ROOT}/interface={IF_NAME_CFG}", data=json.dumps(payload))
    if r.status_code in (200, 204):
        return f"Interface {IF_NAME_MSG} is shutdowned successfully"
    if r.status_code == 404:
        return f"Cannot shutdown: Interface {IF_NAME_MSG}"
    print(f"Disable error: {r.status_code} {r.text}")
    return f"Cannot shutdown: Interface {IF_NAME_MSG}"

def status():
    # อ่าน enabled จาก config
    r_cfg = _request("GET", f"{CFG_ROOT}/interface={IF_NAME_CFG}")
    if r_cfg.status_code == 404:
        return f"No Interface {IF_NAME_MSG}"
    if r_cfg.status_code not in (200,):
        print(f"Status cfg error: {r_cfg.status_code} {r_cfg.text}")
        return f"No Interface {IF_NAME_MSG}"
    enabled = bool(r_cfg.json().get("ietf-interfaces:interface", {}).get("enabled", False))

    # อ่าน oper-status จาก state
    r_state = _request("GET", f"{STATE_ROOT}/interface={IF_NAME_CFG}")
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
        # ถ้า timeout/retry ล้มเหลวครบ จะมาตรงนี้ → ส่งข้อความตามสเปก
        print(f"Exception in handle_command: {e}")
        if cmd == "create":  return f"Cannot create: Interface {IF_NAME_MSG}"
        if cmd == "delete":  return f"Cannot delete: Interface {IF_NAME_MSG}"
        if cmd == "enable":  return f"Cannot enable: Interface {IF_NAME_MSG}"
        if cmd == "disable": return f"Cannot shutdown: Interface {IF_NAME_MSG}"
        if cmd == "status":  return f"No Interface {IF_NAME_MSG}"
        return "Unknown command"
