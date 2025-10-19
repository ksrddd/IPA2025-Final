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
    แล้วส่งไฟล์ .txt กลับไปที่ Webex Room (เพียงครั้งเดียว)
    """
    try:
        # ---- 1) รัน ansible-playbook ----
        base_dir = os.path.dirname(os.path.abspath(__file__))
        ansible_dir = os.path.join(base_dir, "ansible")

        playbook_path = os.path.join(ansible_dir, "playbook.yml")
        hosts_path = os.path.join(ansible_dir, "hosts")
        if not os.path.exists(playbook_path):
            playbook_path = os.path.join(base_dir, "playbook.yml")
            hosts_path = os.path.join(base_dir, "hosts")

        cmd = ["ansible-playbook", "-i", hosts_path, playbook_path]
        result = subprocess.run(cmd, cwd=base_dir, capture_output=True, text=True)
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        print(output)

        # ---- 2) ตรวจผลลัพธ์ ----
        if result.returncode != 0:
            return "Error: Ansible Error"

        # ---- 3) หาไฟล์ที่ถูกสร้าง ----
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
        headers = {"Authorization": f"Bearer {WEBEX_TOKEN}"}

        with open(filepath, "rb") as f:
            files = {
                "roomId": (None, WEBEX_ROOM_ID),
                "text": (None, "show running config"),
                "files": (os.path.basename(filepath), f, "text/plain"),
            }
            resp = requests.post(url, headers=headers, files=files)

        if resp.status_code == 200:
            # ✅ เปลี่ยนข้อความไม่ให้เป็น "ok" ป้องกันส่งซ้ำ
            return "Received message: sent running-config file completed"
        else:
            print("Webex response:", resp.status_code, resp.text)
            return f"Error sending file to Webex (HTTP {resp.status_code})"

    except Exception as e:
        return f"Error (showrun): {str(e)}"
