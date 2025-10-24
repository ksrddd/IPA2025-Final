# ansible_final.py
import os
import subprocess
import tempfile
import requests
from dotenv import load_dotenv
load_dotenv()

WEBEX_TOKEN   = os.environ.get("WEBEX_TOKEN", "")
WEBEX_ROOM_ID = os.environ.get("WEBEX_ROOM_ID", "")
STUDENT_ID    = os.environ.get("STUDENT_ID", "66070315").strip()
ROUTER_NAME   = os.environ.get("ROUTER_NAME", "CSR-1000V").strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANS_DIR  = os.path.join(BASE_DIR, "ansible")
HOSTS    = os.path.join(ANS_DIR, "hosts")
PB_SHOW  = os.path.join(ANS_DIR, "playbook_showrun.yml")   # <-- ใช้ไฟล์แยกสำหรับ showrun

def showrun():
    """
    ดึง 'show running-config' จาก IP ที่กำหนดใน ENV (ROUTER_IP หรือ SHOWRUN_IP)
    แล้วบันทึกเป็นไฟล์ ansible/show_run_{STUDENT_ID}_{ROUTER_NAME}.txt
    จากนั้นอัปโหลดไฟล์ขึ้น Webex
    """
    ip = os.getenv("ROUTER_IP") or os.getenv("SHOWRUN_IP") or ""
    if not ip:
        return "Error: No IP specified"

    # ENV พื้นฐาน
    user    = os.environ.get("ROUTER_USERNAME") or os.environ.get("ROUTER_USER") or "admin"
    pw      = os.environ.get("ROUTER_PASSWORD") or os.environ.get("ROUTER_PASS") or "cisco"
    enablep = os.environ.get("ROUTER_ENABLE", "")

    # ตำแหน่งไฟล์ปลายทาง (ให้ตรงกับที่โค้ดหลักจะไปเปิดใช้งาน)
    base_dir    = os.path.dirname(os.path.abspath(__file__))
    ansible_dir = os.path.join(base_dir, "ansible")
    os.makedirs(ansible_dir, exist_ok=True)
    out_filename = f"show_run_{STUDENT_ID}_{ROUTER_NAME}.txt"
    out_path     = os.path.join(ansible_dir, out_filename)

    # ad-hoc playbook: ใช้ network_cli + cisco.ios.ios_command
    playbook = f"""---
- name: Get running-config
  hosts: all
  gather_facts: no
  connection: network_cli
  collections: [cisco.ios]
  vars:
    ansible_network_os: cisco.ios.ios
    ansible_user: "{user}"
    ansible_password: "{pw}"
    ansible_become: {"yes" if enablep else "no"}
    ansible_become_method: enable
    ansible_become_password: "{enablep}"
    ansible_command_timeout: 120
    ansible_connect_timeout: 60
    # กัน host key checking งอแง
    ansible_ssh_common_args: "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
  tasks:
    - name: Run show running-config
      ios_command:
        commands:
          - show running-config
        wait_for:
          - result[0] contains "end"
        retries: 30
        interval: 5
      register: runout

    - name: Save to file on controller
      delegate_to: localhost
      copy:
        content: "{{{{ runout.stdout[0] }}}}"
        dest: "{out_path}"
        mode: "0644"
"""

    try:
        # เขียน playbook ชั่วคราว
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yml") as f:
            f.write(playbook)
            tmp_play = f.name

        # บังคับ ENV ให้ ansible ไม่เช็ค host key
        env = os.environ.copy()
        env.setdefault("ANSIBLE_HOST_KEY_CHECKING", "False")

        # เรียก ansible-playbook ด้วย ad-hoc inventory "<ip>,"
        cmd = ["ansible-playbook", "-i", f"{ip},", tmp_play]
        result = subprocess.run(cmd, cwd=ansible_dir, capture_output=True, text=True, timeout=300, env=env)
        print((result.stdout or "") + "\n" + (result.stderr or ""))

        if result.returncode != 0:
            return "Error: Ansible Error"

        if not os.path.exists(out_path):
            return f"Error: File {out_filename} not found"

        # อัปโหลดไฟล์ขึ้น Webex
        url = "https://webexapis.com/v1/messages"
        headers = {"Authorization": f"Bearer {WEBEX_TOKEN}"}
        with open(out_path, "rb") as f:
            files = {
                "roomId": (None, WEBEX_ROOM_ID),
                "text": (None, "show running config"),
                "files": (out_filename, f, "text/plain"),
            }
            resp = requests.post(url, headers=headers, files=files)

        return ("Received message: sent running-config file completed"
                if resp.status_code == 200
                else f"Error sending file to Webex (HTTP {resp.status_code})")
    except Exception as e:
        return f"Error (showrun): {e}"



def set_motd(router_ip: str, text: str) -> bool:
    """
    ตั้งค่า banner MOTD ด้วย Ansible collection cisco.ios (ad-hoc playbook)
    - inventory ad-hoc "<ip>,"
    - ใช้ block scalar (|-) รองรับเครื่องหมายคำพูด/หลายบรรทัด
    - รองรับ enable password ถ้าตั้ง ROUTER_ENABLE ไว้
    """
    user    = os.environ.get("ROUTER_USERNAME") or os.environ.get("ROUTER_USER") or "admin"
    pw      = os.environ.get("ROUTER_PASSWORD") or os.environ.get("ROUTER_PASS") or "cisco"
    enablep = os.environ.get("ROUTER_ENABLE", "")

    indented = "\n".join(("          " + line) for line in text.splitlines()) if text else "          "
    play = f"""---
- name: Configure MOTD
  hosts: all
  gather_facts: no
  connection: network_cli
  collections: [cisco.ios]
  vars:
    ansible_network_os: cisco.ios.ios
    ansible_user: {user}
    ansible_password: {pw}
    ansible_become: {"yes" if enablep else "no"}
    ansible_become_method: enable
    ansible_become_password: {enablep if enablep else '""'}
    ansible_command_timeout: 120
    ansible_connect_timeout: 60
  tasks:
    - name: Set banner MOTD
      ios_banner:
        banner: motd
        state: present
        text: |-
{indented}
"""
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yml") as f:
            f.write(play)
            tmp_play = f.name
        r = subprocess.run(
            ["ansible-playbook", "-i", f"{router_ip},", tmp_play],
            capture_output=True, text=True, timeout=300
        )
        if r.returncode != 0:
            print("[ansible motd] rc=", r.returncode)
            print(r.stdout)
            print(r.stderr)
        return r.returncode == 0
    except Exception as e:
        print("ansible motd error:", e)
        return False

# alias ให้สคริปต์หลักเรียกชื่อเดิมได้
def set_motd_via_ansible(router_ip: str, text: str) -> bool:
    return set_motd(router_ip, text)
