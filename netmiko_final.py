from netmiko import ConnectHandler
import os
import re
from typing import Optional

USERNAME = os.environ.get("ROUTER_USER") or os.environ.get("ROUTER_USERNAME") or "admin"
PASSWORD = os.environ.get("ROUTER_PASS") or os.environ.get("ROUTER_PASSWORD") or "cisco"

def _device(ip: str) -> dict:
    return {
        "device_type": "cisco_ios",
        "host": ip,
        "username": USERNAME,
        "password": PASSWORD,
        "fast_cli": True,
    }

def gigabit_status(ip: str) -> str:
    """
    สรุปสถานะทั้ง GigabitEthernet* และ Loopback* จาก 'show ip interface brief'
    ตัวอย่างผลลัพธ์:
      GigabitEthernet1 up, GigabitEthernet2 administratively down, Loopback66070315 up
      -> Gi: 1 up, 0 down, 1 admin-down | Lo: 1 up, 0 down, 0 admin-down
    """
    with ConnectHandler(**_device(ip)) as ssh:
        gi_up = gi_down = gi_admin = 0
        lo_up = lo_down = lo_admin = 0
        lines_out = []

        # พยายามใช้ TextFSM ก่อน (ถ้ามี ntc_templates)
        res = ssh.send_command("show ip interface brief", use_textfsm=True)

        def _acc(name: str, status: str, proto: str):
            nonlocal gi_up, gi_down, gi_admin, lo_up, lo_down, lo_admin
            status_l = (status or "").lower()
            proto_l = (proto or "").lower()
            is_admin = "administratively" in status_l
            is_up = (status_l == "up") and (proto_l in ("up", ""))

            if name.startswith("GigabitEthernet"):
                if is_admin:
                    gi_admin += 1; lines_out.append(f"{name} administratively down")
                elif is_up:
                    gi_up += 1;    lines_out.append(f"{name} up")
                else:
                    gi_down += 1;  lines_out.append(f"{name} down")
            elif name.startswith("Loopback"):
                if is_admin:
                    lo_admin += 1; lines_out.append(f"{name} administratively down")
                elif is_up:
                    lo_up += 1;    lines_out.append(f"{name} up")
                else:
                    lo_down += 1;  lines_out.append(f"{name} down")

        if isinstance(res, list):
            # โหมด parsed (list[dict])
            for it in res:
                name   = it.get("intf") or it.get("interface") or ""
                if not (name.startswith("GigabitEthernet") or name.startswith("Loopback")):
                    continue
                status = it.get("status") or it.get("Status") or ""
                proto  = it.get("proto")  or it.get("protocol") or ""
                _acc(name, status, proto)
        else:
            # โหมดข้อความดิบ
            raw = res if isinstance(res, str) else ssh.send_command("show ip interface brief")
            for line in raw.splitlines():
                line = line.strip()
                if not (line.startswith("GigabitEthernet") or line.startswith("Loopback")):
                    continue
                cols = line.split()
                if len(cols) < 3:
                    continue
                name = cols[0]
                if "administratively down" in line.lower():
                    status, proto = "administratively down", cols[-1]
                else:
                    status, proto = cols[-2], cols[-1]
                _acc(name, status, proto)

        summary = (
            f"Gi: {gi_up} up, {gi_down} down, {gi_admin} admin-down | "
            f"Lo: {lo_up} up, {lo_down} down, {lo_admin} admin-down"
        )
        return f"{', '.join(lines_out)} -> {summary}"

# รองรับการเรียกชื่ออื่น (เช่น gigabit_status_for_ip)
def gigabit_status_for_ip(ip: str) -> str:
    return gigabit_status(ip)


def _clean_banner(s: str) -> str:
    s = s.strip()
    s = re.sub(r"(?i)^message of the day is\s*:?\s*", "", s)
    s = re.sub(r"(?i)^motd banner.*\n", "", s)
    return s.strip()

def read_motd(ip: str) -> Optional[str]:
    """
    อ่านค่า MOTD ด้วย Netmiko/TextFSM:
      - ถ้ามี MOTD → คืนข้อความ (string)
      - ถ้าไม่มี / อ่านไม่ได้ → คืน None 
    """
    try:
        with ConnectHandler(**_device(ip)) as ssh:
            # 1) show running-config | section banner
            out = ssh.send_command("show running-config | section banner")
            if out and "banner motd" in out.lower():
                m = re.search(r"(?is)banner\s+motd\s+(\S)\s+(.*?)\1", out)
                if m and m.group(2).strip():
                    return _clean_banner(m.group(2))

            # 2) fallback: show banner motd
            out2 = ssh.send_command("show banner motd")
            if out2 and "not configured" not in out2.lower():
                text = _clean_banner(out2)
                return text if text else None

            return None
    except Exception:
        return None
