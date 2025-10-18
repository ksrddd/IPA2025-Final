# gigabit_status function using Netmiko
from netmiko import ConnectHandler
import os

device_ip = os.environ.get("ROUTER_IP", "10.0.15.63")
username = os.environ.get("ROUTER_USER", "admin")
password = os.environ.get("ROUTER_PASS", "cisco")

device_params = {
    "device_type": "cisco_ios",   # <!!!REPLACEME with device type for netmiko!!!>
    "ip": device_ip,
    "username": username,
    "password": password,
}


def gigabit_status():
    ans = ""
    with ConnectHandler(**device_params) as ssh:
        up = down = admin_down = 0

        # พยายามใช้ TextFSM ก่อน
        result = ssh.send_command("show ip interface brief", use_textfsm=True)

        iface_list = []

        if isinstance(result, list):
            # โหมด parsed โดย TextFSM: list[dict]
            for item in result:
                # ดึงชื่ออินเทอร์เฟซ/สถานะ/โปรโตคอลแบบยืดหยุ่น
                name   = item.get("intf") or item.get("interface") or ""
                status = (item.get("status") or item.get("Status") or "").lower()
                proto  = (item.get("proto")  or item.get("protocol") or "").lower()

                if not name.startswith("GigabitEthernet"):
                    continue

                # normalize status
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
            # Fallback: พาร์สข้อความดิบ
            raw = result if isinstance(result, str) else ssh.send_command("show ip interface brief")
            for line in raw.splitlines():
                line = line.strip()
                if not line.startswith("GigabitEthernet"):
                    continue
                cols = line.split()
                name = cols[0]
                # โปรโตคอลคือคอลัมน์สุดท้ายเสมอ
                proto = cols[-1].lower()
                # สถานะก่อนสุดท้าย อาจเป็นคำเดียว (up/down) หรือสองคำ ("administratively down")
                if "administratively" in line:
                    status = "administratively down"
                else:
                    status = cols[-2].lower()

                if status == "administratively down":
                    iface_list.append(f"{name} administratively down")
                    admin_down += 1
                elif status == "up" and (proto == "up" or proto == ""):
                    iface_list.append(f"{name} up")
                    up += 1
                else:
                    iface_list.append(f"{name} down")
                    down += 1

        iface_summary = ", ".join(iface_list)
        ans = f"{iface_summary} -> {up} up, {down} down, {admin_down} administratively down"
        print(ans)
        return ans

