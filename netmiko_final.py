# netmiko_final.py
from netmiko import ConnectHandler
import os
import re

# รองรับได้ทั้งคู่: ROUTER_USERNAME/ROUTER_PASSWORD และ ROUTER_USER/ROUTER_PASS
USERNAME = os.environ.get("ROUTER_USERNAME") or os.environ.get("ROUTER_USER") or "admin"
PASSWORD = os.environ.get("ROUTER_PASSWORD") or os.environ.get("ROUTER_PASS") or "cisco"

def _device(ip: str) -> dict:
    return {
        "device_type": "cisco_ios",
        "host": ip,                # ใช้ host ตามสเปคใหม่
        "username": USERNAME,
        "password": PASSWORD,
        "fast_cli": False,
        "global_delay_factor": 1,
        "use_keys": False,
        "allow_agent": False,
    }

def gigabit_status(ip: str) -> str:
    """
    แสดงสถานะของทั้ง GigabitEthernet และ Loopback interface ทั้งหมด
    เช่น GigabitEthernet1 up, Loopback66070315 up -> 2 up, 0 down, 0 administratively down
    """
    from netmiko import ConnectHandler
    with ConnectHandler(**_device(ip)) as ssh:
        up = down = admin_down = 0
        result = ssh.send_command("show ip interface brief", use_textfsm=True)
        iface_list = []

        if isinstance(result, list):
            for item in result:
                name   = item.get("intf") or item.get("interface") or ""
                status = (item.get("status") or item.get("Status") or "").lower()
                proto  = (item.get("proto")  or item.get("protocol") or "").lower()

                # สนใจเฉพาะ GigabitEthernet และ Loopback
                if not (name.startswith("GigabitEthernet") or name.startswith("Loopback")):
                    continue

                if "administratively" in status:
                    iface_list.append(f"{name} administratively down")
                    admin_down += 1
                elif status == "up" and (proto == "up" or proto == ""):
                    iface_list.append(f"{name} up")
                    up += 1
                else:
                    iface_list.append(f"{name} down")
                    down += 1
        else:
            raw = result if isinstance(result, str) else ssh.send_command("show ip interface brief")
            for line in raw.splitlines():
                line = line.strip()
                if not (line.startswith("GigabitEthernet") or line.startswith("Loopback")):
                    continue
                cols = line.split()
                name = cols[0]
                if "administratively" in line.lower():
                    status = "administratively down"
                else:
                    status = cols[-2].lower()
                proto = cols[-1].lower()
                if status == "administratively down":
                    iface_list.append(f"{name} administratively down")
                    admin_down += 1
                elif status == "up" and (proto == "up" or proto == ""):
                    iface_list.append(f"{name} up")
                    up += 1
                else:
                    iface_list.append(f"{name} down")
                    down += 1

        # รวมผลลัพธ์ทั้งหมด
        return f"{', '.join(iface_list)} -> {up} up, {down} down, {admin_down} administratively down"

def _strip_banner_wrappers(s: str) -> str:
    s = s.strip()
    s = re.sub(r"(?i)^message of the day is\s*:?\s*", "", s)
    s = re.sub(r"(?i)^motd banner.*\n", "", s)
    return s.strip()

def read_motd(ip: str) -> str | None:
    """
    คืนข้อความ MOTD (ถ้ามี).
    ถ้าเชื่อมต่อไม่ได้ / ไม่มี MOTD ให้คืน None (เพื่อให้โค้ดหลักตอบ "Error: No MOTD Configured")
    """
    try:
        with ConnectHandler(**_device(ip)) as ssh:
            out = ssh.send_command("show running-config | section banner")
            low = out.lower()
            if "banner motd" in low:
                lines = out.splitlines()
                try:
                    idx = next(i for i, l in enumerate(lines) if l.lower().startswith("banner motd"))
                    header = lines[idx]
                    after = header.split("motd", 1)[1].strip()
                    delim = after[:2] if after.startswith("^") else after[:1]
                    joined = "\n".join(lines[idx:])
                    s = joined.find(delim)
                    e = joined.find(delim, s + len(delim)) if s != -1 else -1
                    if s != -1 and e != -1:
                        body = joined[s + len(delim):e].strip()
                        return body if body else None
                except Exception:
                    pass

            out2 = ssh.send_command("show banner motd")
            if out2 and "not configured" not in out2.lower():
                return out2.strip()
            return None
    except Exception:
        return None

# ----- aliases ให้สคริปต์หลักเรียกชื่อเดิมได้ -----
def gigabit_status_for_ip(ip: str) -> str:
    return gigabit_status(ip)

def read_motd_via_netmiko(ip: str) -> str | None:
    return read_motd(ip)

# (optional) เผื่อสคริปต์อื่นเรียก showrun_for_ip ในอนาคต
def showrun_for_ip(ip: str, outfile: str | None = None) -> str:
    with ConnectHandler(**_device(ip)) as ssh:
        out = ssh.send_command("show running-config", expect_string=r"#|\$")
    import os
    os.makedirs("outputs", exist_ok=True)
    path = outfile or os.path.join("outputs", f"{ip}-running-config.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    return path
