import os
import subprocess
import requests
from dotenv import load_dotenv, find_dotenv

# โหลดค่าจากไฟล์ .env
load_dotenv(find_dotenv())

WEBEX_TOKEN = os.getenv("WEBEX_TOKEN")
WEBEX_ROOM_ID = os.getenv("WEBEX_ROOM_ID")
STUDENT_ID = os.getenv("STUDENT_ID")
ROUTER_NAME = "R3-Exam"   # เปลี่ยนตาม Pod ของคุณ

def showrun():
    """
    เรียก ansible-playbook เพื่อ backup running-config
    แล้วส่งไฟล์ .txt กลับไปที่ Webex Room
    """
    try:
        # ---- 1) รัน ansible-playbook (ตั้ง cwd ให้ถูก) ----
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ansible_dir = os.path.join(base_dir, "ansible")

        # ถ้าไฟล์อยู่ใต้ ansible/ ให้รันจากตรงนั้น
        playbook_path = os.path.join(ansible_dir, "playbook.yml")
        hosts_path = os.path.join(ansible_dir, "hosts")
        if not os.path.exists(playbook_path):
            # เผื่อคุณวาง playbook ไว้รากโปรเจกต์
            playbook_path = os.path.join(base_dir, "playbook.yml")
            hosts_path = os.path.join(base_dir, "hosts")

        cmd = ["ansible-playbook", "-i", hosts_path, playbook_path]
        result = subprocess.run(cmd, cwd=base_dir, capture_output=True, text=True)
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        print(output)

        # ---- 2) ตรวจผลลัพธ์ว่าผ่านไหม ----
        # ใช้ returncode เป็นหลัก และกันเคสที่ stdout ไม่มีคำว่า failed=0
        if result.returncode != 0:
            return "Error: Ansible"

        # ---- 3) หาไฟล์ที่ถูกสร้างจริง (เช็คทั้งรากและ ansible/) ----
        filename = f"show_run_{STUDENT_ID}_{ROUTER_NAME}.txt"
        candidates = [
            os.path.join(base_dir, filename),
            os.path.join(ansible_dir, filename),
        ]
        filepath = next((p for p in candidates if os.path.exists(p)), None)
        if not filepath:
            return f"Error: File {filename} not found"

        # ---- 4) ส่งไฟล์กลับไปยัง Webex Room ----
        print(f"Sending {filepath} to Webex room...")

        url = "https://webexapis.com/v1/messages"
        # ✅ ต้องมี Bearer นำหน้า token
        headers = {"Authorization": f"Bearer {WEBEX_TOKEN}"}

        with open(filepath, "rb") as f:
            files = {
                "roomId": (None, WEBEX_ROOM_ID),
                "text": (None, "show running config"),
                "files": (os.path.basename(filepath), f, "text/plain"),
            }
            resp = requests.post(url, headers=headers, files=files)

        if resp.status_code == 200:
            return "ok"
        else:
            print("Webex response:", resp.status_code, resp.text)
            return f"Error sending file to Webex (HTTP {resp.status_code})"

    except Exception as e:
        return f"Error (showrun): {str(e)}"
