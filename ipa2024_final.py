#######################################################################################
# Yourname: Sukhum Rudeemaetakul
# Your student ID: 66070315
# Your GitHub Repo: 
#######################################################################################

# 1. Import libraries for API requests, JSON formatting, time, os,
#    (restconf_final or netconf_final), netmiko_final, and ansible_final.

import os
import time
import json
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
from dotenv import load_dotenv
load_dotenv()

# ใช้ RESTCONF ตามที่ทำไว้ (ถ้าใช้ NETCONF ให้เปลี่ยน import ตรงนี้)
import restconf_final
import netmiko_final
import ansible_final

#######################################################################################
# 2. Assign the Webex access token to the variable ACCESS_TOKEN using environment variables.

ACCESS_TOKEN = os.environ.get("WEBEX_TOKEN", "")

# (แนะนำเพิ่มตัวแปรจาก ENV เพื่อใช้ตรวจ prefix คำสั่ง และห้อง Webex)
STUDENT_ID = os.environ.get("STUDENT_ID", "").strip()
if not STUDENT_ID:
    raise RuntimeError("Missing STUDENT_ID in environment variables.")

#######################################################################################
# 3. Prepare parameters get the latest message for messages API.

# Defines a variable that will hold the roomId
roomIdToGetMessages = os.environ.get("WEBEX_ROOM_ID", "")
if not roomIdToGetMessages:
    raise RuntimeError("Missing WEBEX_ROOM_ID in environment variables.")

while True:
    # always add 1 second of delay to the loop to not go over a rate limit of API calls
    time.sleep(1)

    # the Webex Teams GET parameters
    #  "roomId" is the ID of the selected room
    #  "max": 1  limits to get only the very last message in the room
    getParameters = {"roomId": roomIdToGetMessages, "max": 1}

    # the Webex Teams HTTP header, including the Authoriztion
    getHTTPHeader = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

    # 4. Provide the URL to the Webex Teams messages API, and extract location from the received message.

    # Send a GET request to the Webex Teams messages API.
    # - Use the GetParameters to get only the latest message.
    # - Store the message in the "r" variable.
    r = requests.get(
        "https://webexapis.com/v1/messages",
        params=getParameters,
        headers=getHTTPHeader,
    )
    # verify if the retuned HTTP status code is 200/OK
    if not r.status_code == 200:
        raise Exception(
            "Incorrect reply from Webex Teams API. Status code: {}".format(r.status_code)
        )

    # get the JSON formatted returned data
    json_data = r.json()

    # check if there are any messages in the "items" array
    if len(json_data["items"]) == 0:
        raise Exception("There are no messages in the room.")

    # store the array of messages
    messages = json_data["items"]

    # store the text of the first message in the array
    message = messages[0].get("text", "")
    print("Received message: " + message)

    # check if the text of the message starts with the magic character "/"
    # followed by your studentID and a space and followed by a command name
    #  e.g.  "/66070123 create"
    if message.startswith(f"/{STUDENT_ID} "):

        # extract the command
        command = message.split(maxsplit=1)[1].strip().lower()
        print(command)

        # 5. Complete the logic for each command

        if command == "create":
            responseMessage = restconf_final.handle_command("create")
        elif command == "delete":
            responseMessage = restconf_final.handle_command("delete")
        elif command == "enable":
            responseMessage = restconf_final.handle_command("enable")
        elif command == "disable":
            responseMessage = restconf_final.handle_command("disable")
        elif command == "status":
            responseMessage = restconf_final.handle_command("status")
        elif command == "gigabit_status":
            responseMessage = netmiko_final.gigabit_status()
        elif command == "showrun":
            # showrun() ของคุณรีเทิร์น "ok" เมื่อ playbook สำเร็จ
            responseMessage = ansible_final.showrun()
        else:
            responseMessage = "Error: No command or unknown command"

        # 6. Complete the code to post the message to the Webex Teams room.

        # The Webex Teams POST JSON data for command showrun
        # - "roomId" is is ID of the selected room
        # - "text": is always "show running config"
        # - "files": is a tuple of filename, fileobject, and filetype.

        # the Webex Teams HTTP headers, including the Authoriztion and Content-Type

        # Prepare postData and HTTPHeaders for command showrun
        # Need to attach file if responseMessage is 'ok';
        # Read Send a Message with Attachments Local File Attachments
        # https://developer.webex.com/docs/basics for more detail

        if command == "showrun" and responseMessage == "ok":
            # ตั้งชื่อไฟล์ที่ playbook เซฟไว้ เช่น show_run_<studentID>_<router>.txt
            router_name = "R3-Exam"   # ให้ตรงกับที่ playbook ตั้งชื่อ
            filename = f"show_run_{STUDENT_ID}_{router_name}.txt"

            # เผื่อไฟล์อยู่ใน ./ หรือ ./ansible/
            candidates = [filename, os.path.join("ansible", filename)]
            filepath = next((p for p in candidates if os.path.exists(p)), None)

            if not filepath:
                # ไม่พบไฟล์ -> แจ้ง Error แบบข้อความ
                postData = {"roomId": roomIdToGetMessages, "text": "Error: Ansible"}
                r = requests.post(
                    "https://webexapis.com/v1/messages",
                    data=json.dumps(postData),
                    headers={
                        "Authorization": f"Bearer {ACCESS_TOKEN}",
                        "Content-Type": "application/json",
                    },
                )
                if r.status_code != 200:
                    raise Exception(
                        f"Incorrect reply from Webex Teams API. Status code: {r.status_code}"
                    )
            else:
                filetype = "text/plain"
                with open(filepath, "rb") as fileobject:
                    postData = MultipartEncoder({
                        "roomId": roomIdToGetMessages,
                        "text": "show running config",
                        "files": (os.path.basename(filepath), fileobject, filetype),
                    })
                    HTTPHeaders = {
                        # ✅ เติม Bearer เพื่อแก้ 401
                        "Authorization": f"Bearer {ACCESS_TOKEN}",
                        "Content-Type": postData.content_type,
                    }
                    r = requests.post(
                        "https://webexapis.com/v1/messages",
                        data=postData,
                        headers=HTTPHeaders,
                    )
                    if r.status_code != 200:
                        raise Exception(
                            f"Incorrect reply from Webex Teams API. Status code: {r.status_code}"
                        )
        else:
            # other commands only send text, or showrun fail -> ส่งข้อความธรรมดา
            postData = {"roomId": roomIdToGetMessages, "text": responseMessage}
            r = requests.post(
                "https://webexapis.com/v1/messages",
                data=json.dumps(postData),
                headers={
                    # ✅ เติม Bearer เพื่อแก้ 401
                    "Authorization": f"Bearer {ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
            )
            if r.status_code != 200:
                raise Exception(
                    f"Incorrect reply from Webex Teams API. Status code: {r.status_code}"
                )
