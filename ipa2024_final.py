#######################################################################################
# Yourname: Sukhum Rudeemaetakul
# Your student ID: 66070315
# Your GitHub Repo: https://github.com/ksrddd/IPA2025-Final.git
#######################################################################################

import os
import time
import json
import requests
from dotenv import load_dotenv
load_dotenv()

import restconf_final
import netconf_final
import netmiko_final
import ansible_final

ACCESS_TOKEN = os.environ.get("WEBEX_TOKEN", "")
STUDENT_ID = os.environ.get("STUDENT_ID", "").strip()
if not STUDENT_ID:
    raise RuntimeError("Missing STUDENT_ID in environment variables.")

roomIdToGetMessages = os.environ.get("WEBEX_ROOM_ID", "")
if not roomIdToGetMessages:
    raise RuntimeError("Missing WEBEX_ROOM_ID in environment variables.")

# ============================ CONFIG ============================
ALLOWED_IPS = {"10.0.15.61", "10.0.15.62", "10.0.15.63", "10.0.15.64", "10.0.15.65"}
CURRENT_METHOD = None   # "restconf" | "netconf"
# ===============================================================

def set_method(m):
    global CURRENT_METHOD
    if m not in ("restconf", "netconf"):
        return "Error: No method specified"
    CURRENT_METHOD = m
    return "Ok: Restconf" if m == "restconf" else "Ok: Netconf"

def dispatch_command(method: str, router_ip: str, cmd: str, args: list[str]) -> str:
    """ส่งต่อคำสั่งไปยังโมดูลตาม method (ส่วนที่ 1)"""
    label = "Restconf" if method == "restconf" else "Netconf"

    if method == "restconf":
        base = restconf_final.handle_command(cmd, router_ip)
    else:
        base = netconf_final.handle_command(cmd, router_ip)

    if cmd in ("create", "delete", "enable", "disable"):
        if "successfully" in base:
            return f"{base} using {label}"
        if cmd == "disable" and base.startswith("Cannot shutdown:"):
            return f"{base} (checked by {label})"
        return base
    if cmd == "status":
        return f"{base} (checked by {label})"
    return base


# ===============================================================
# MAIN LOOP
# ===============================================================
while True:
    time.sleep(1)
    getParameters = {"roomId": roomIdToGetMessages, "max": 1}
    getHTTPHeader = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    r = requests.get("https://webexapis.com/v1/messages",
                     params=getParameters, headers=getHTTPHeader)
    if r.status_code != 200:
        continue

    data = r.json()
    items = data.get("items", [])
    if not items:
        continue

    message = items[0].get("text", "") or ""
    print("Received message:", message)

    if not message.startswith(f"/{STUDENT_ID}"):
        continue

    tail = message[len(f"/{STUDENT_ID}"):].strip()
    if not tail:
        continue

    tokens = tail.split()
    reply = None  # ถ้า None จะไม่ส่งโพสต์ซ้ำ (เช่น showrun ที่ส่งไฟล์ในฟังก์ชันแล้ว)

    # --- /SID showrun (ไม่มี IP) ---
    if len(tokens) == 1 and tokens[0].lower() == "showrun":
        reply = "Error: No IP specified"

    # --- /SID restconf | netconf ---
    elif len(tokens) == 1 and tokens[0].lower() in ("restconf", "netconf"):
        reply = set_method(tokens[0].lower())

    # --- /SID <IP> ---
    elif len(tokens) == 1 and tokens[0].count(".") == 3:
        reply = "Error: No command found."

    # --- /SID <IP> <command> [args...] ---
    elif tokens[0].count(".") == 3 and len(tokens) >= 2:
        ip  = tokens[0]
        cmd = tokens[1].lower()
        args = tokens[2:]

        # ✅ MOTD — ใช้ได้กับทุก IP (ตามข้อสอบ)
        if cmd == "motd":
            if args:
                ok = ansible_final.set_motd(ip, " ".join(args))
                reply = "Ok: success" if ok else "Error: failed to configure MOTD"
            else:
                motd = netmiko_final.read_motd(ip)
                reply = motd if motd else "Error: No MOTD Configured"

        # จากนี้ไป: ต้องเป็น IP target เท่านั้น
        elif cmd in ("gigabit_status", "gi-status", "gigabit"):
            if ip not in ALLOWED_IPS:
                reply = "Error: No IP specified"
            else:
                result = netmiko_final.gigabit_status(ip)
                reply = result or "Error: gi-status failed"

        elif cmd in ("showrun", "show-run"):
            if ip not in ALLOWED_IPS:
                reply = "Error: No IP specified"
            else:
                os.environ["ROUTER_IP"] = ip
                _ = ansible_final.showrun()   # ฟังก์ชันนี้จะโพสต์ไฟล์ + "show running config" เอง
                reply = None

        else:
            if ip not in ALLOWED_IPS:
                reply = "Error: No IP specified"
            elif CURRENT_METHOD is None:
                reply = "Error: No method specified"
            else:
                reply = dispatch_command(CURRENT_METHOD, ip, cmd, args)

    else:
        reply = "Error: No IP specified"

    if reply is not None:
        postData = {"roomId": roomIdToGetMessages, "text": reply}
        rr = requests.post("https://webexapis.com/v1/messages",
                           data=json.dumps(postData),
                           headers={"Authorization": f"Bearer {ACCESS_TOKEN}",
                                    "Content-Type": "application/json"})
        if rr.status_code != 200:
            print(f"Error sending message: {rr.status_code}")
