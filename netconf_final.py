# netconf_final.py
from ncclient import manager
import xmltodict
import os

STUDENT_ID = os.environ.get("STUDENT_ID", "66070315").strip()
IF_NAME_CFG = f"Loopback{STUDENT_ID}"
IF_NAME_MSG = f"loopback {STUDENT_ID}"

NETCONF_PORT = int(os.environ.get("NETCONF_PORT", "830"))
USERNAME = os.environ.get("ROUTER_USER", "admin")
PASSWORD = os.environ.get("ROUTER_PASS", "cisco")

def ip_for_student(student_id: str) -> str:
    last3 = student_id[-3:]
    x = int(last3[0])
    y = int(last3[1:])
    return f"172.{x}.{y}.1"

LOOPBACK_IP = ip_for_student(STUDENT_ID)

def _connect(ip: str):
    return manager.connect(
        host=ip,
        port=NETCONF_PORT,
        username=USERNAME,
        password=PASSWORD,
        hostkey_verify=False,
        allow_agent=False,
        look_for_keys=False,
        timeout=10
    )

def has_interface(ip: str) -> bool:
    with _connect(ip) as m:
        filt = f"""
<filter>
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{IF_NAME_CFG}</name>
    </interface>
  </interfaces>
</filter>
"""
        resp = m.get_config(source="running", filter=filt)
        d = xmltodict.parse(resp.xml)
        return IF_NAME_CFG in resp.xml and d is not None

def create(ip: str) -> str:
    cfg = f"""
<config>
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{IF_NAME_CFG}</name>
      <description>Student {STUDENT_ID} loopback</description>
      <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:softwareLoopback</type>
      <enabled>true</enabled>
      <ipv4 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip">
        <address>
          <ip>{LOOPBACK_IP}</ip>
          <netmask>255.255.255.0</netmask>
        </address>
      </ipv4>
    </interface>
  </interfaces>
</config>
"""
    with _connect(ip) as m:
        r = m.edit_config(target="running", config=cfg)
        return f"Interface {IF_NAME_MSG} is created successfully" if "<ok/>" in r.xml else f"Cannot create: Interface {IF_NAME_MSG}"

def delete(ip: str) -> str:
    cfg = f"""
<config>
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface operation="delete">
      <name>{IF_NAME_CFG}</name>
    </interface>
  </interfaces>
</config>
"""
    with _connect(ip) as m:
        r = m.edit_config(target="running", config=cfg)
        return f"Interface {IF_NAME_MSG} is deleted successfully" if "<ok/>" in r.xml else f"Cannot delete: Interface {IF_NAME_MSG}"

def enable(ip: str) -> str:
    cfg = f"""
<config>
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{IF_NAME_CFG}</name>
      <enabled>true</enabled>
    </interface>
  </interfaces>
</config>
"""
    with _connect(ip) as m:
        r = m.edit_config(target="running", config=cfg)
        return f"Interface {IF_NAME_MSG} is enabled successfully" if "<ok/>" in r.xml else f"Cannot enable: Interface {IF_NAME_MSG}"

def disable(ip: str) -> str:
    cfg = f"""
<config>
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{IF_NAME_CFG}</name>
      <enabled>false</enabled>
    </interface>
  </interfaces>
</config>
"""
    with _connect(ip) as m:
        r = m.edit_config(target="running", config=cfg)
        return f"Interface {IF_NAME_MSG} is shutdowned successfully" if "<ok/>" in r.xml else f"Cannot shutdown: Interface {IF_NAME_MSG}"

def status(ip: str) -> str:
    with _connect(ip) as m:
        filt = f"""
<filter>
  <interfaces-state xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{IF_NAME_CFG}</name>
    </interface>
  </interfaces-state>
</filter>
"""
        r = m.get(filt)
        d = xmltodict.parse(r.xml)
        # ถ้าไม่มีข้อมูล state → อาจไม่มี interface
        if "interfaces-state" not in r.xml:
            return f"No Interface {IF_NAME_MSG}"

        try:
            iface = d["rpc-reply"]["data"]["interfaces-state"]["interface"]
            # ถ้าเป็น list ให้เอาตัวแรก
            if isinstance(iface, list):
                iface = iface[0]
            oper = iface.get("oper-status", "down")
        except Exception:
            return f"No Interface {IF_NAME_MSG}"

        # อ่าน enabled จาก running-config
        filt2 = f"""
<filter>
  <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
    <interface>
      <name>{IF_NAME_CFG}</name>
    </interface>
  </interfaces>
</filter>
"""
        r2 = m.get_config(source="running", filter=filt2)
        if IF_NAME_CFG not in r2.xml:
            return f"No Interface {IF_NAME_MSG}"
        d2 = xmltodict.parse(r2.xml)
        iface2 = d2["rpc-reply"]["data"]["interfaces"]["interface"]
        enabled = str(iface2.get("enabled", "false")).lower() == "true"

        if enabled and oper == "up":
            return f"Interface {IF_NAME_MSG} is enabled"
        if not enabled:
            return f"Interface {IF_NAME_MSG} is disabled"
        return f"Interface {IF_NAME_MSG} admin={'up' if enabled else 'down'}, oper={oper}"

def handle_command(cmd: str, router_ip: str) -> str:
    try:
        if cmd == "create":
            return create(router_ip) if not has_interface(router_ip) else f"Cannot create: Interface {IF_NAME_MSG}"
        if cmd == "delete":
            return delete(router_ip) if has_interface(router_ip) else f"Cannot delete: Interface {IF_NAME_MSG}"
        if cmd == "enable":
            return enable(router_ip) if has_interface(router_ip) else f"Cannot enable: Interface {IF_NAME_MSG}"
        if cmd == "disable":
            return disable(router_ip) if has_interface(router_ip) else f"Cannot shutdown: Interface {IF_NAME_MSG}"
        if cmd == "status":
            return status(router_ip)
        return "Unknown command"
    except Exception:
        if cmd == "create":  return f"Cannot create: Interface {IF_NAME_MSG}"
        if cmd == "delete":  return f"Cannot delete: Interface {IF_NAME_MSG}"
        if cmd == "enable":  return f"Cannot enable: Interface {IF_NAME_MSG}"
        if cmd == "disable": return f"Cannot shutdown: Interface {IF_NAME_MSG}"
        if cmd == "status":  return f"No Interface {IF_NAME_MSG}"
        return "Unknown command"
