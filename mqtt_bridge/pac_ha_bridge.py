#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pont PAC piscine (POWER S / AXEN) -> MQTT / Home Assistant.

Ecoute passivement le bus RS485 (Modbus RTU) via une passerelle EW11 en mode
transparent (TCP server), decode tous les parametres connus, et les publie en
MQTT avec auto-decouverte Home Assistant : toutes les entites apparaissent
automatiquement, regroupees sous un appareil "PAC Piscine".

Lecture seule (monitoring). Dependance : paho-mqtt  (pip install paho-mqtt)

Auteur : reverse-engineering EW11 + decompilation app DOTELS/AXEN.
"""
import socket, time, json, sys, threading

# ============================ CONFIGURATION ============================
EW11_HOST   = "192.168.1.150"   # IP de la passerelle EW11
EW11_PORT   = 8899              # port TCP (mode transparent / None)

MQTT_HOST   = "192.168.1.10"    # <-- IP de ton broker MQTT (Mosquitto / HA)
MQTT_PORT   = 1883
MQTT_USER   = "mqtt"            # <-- identifiant MQTT (ou "" si anonyme)
MQTT_PASS   = "motdepasse"      # <-- mot de passe MQTT

PUBLISH_EVERY = 10              # publie l'etat toutes les N secondes
DEVICE_ID   = "pac_piscine"     # identifiant unique de l'appareil dans HA
DEVICE_NAME = "PAC Piscine"
DISC_PREFIX = "homeassistant"   # prefixe de decouverte HA (defaut)
BASE        = "pac"             # prefixe des topics d'etat
# =======================================================================

STATE_TOPIC = f"{BASE}/state"
AVAIL_TOPIC = f"{BASE}/availability"

MODES = {1: "Froid", 2: "Chaud", 4: "Auto"}
FUNCS = {0: "Smart", 0x10: "Silence", 0x400: "Boost"}

# ---------------- decodage Modbus RTU ----------------
def crc_ok(f):
    if len(f) < 4: return False
    c = 0xFFFF
    for x in f[:-2]:
        c ^= x
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return (c & 0xFF) == f[-2] and (c >> 8) == f[-1]

def next_frame(b, i):
    n = len(b)
    if i + 4 > n: return None
    fc = b[i+1]; cands = []
    if fc in (1, 2, 3, 4):
        cands.append(8)
        if i+3 <= n: cands.append(3 + b[i+2] + 2)
    if fc == 16:
        cands.append(8)
        if i+7 <= n: cands.append(7 + b[i+6] + 2)
    if fc in (5, 6): cands.append(8)
    if fc & 0x80: cands.append(5)
    for L in sorted(set(cands)):
        if i+L <= n and crc_ok(b[i:i+L]): return b[i:i+L]
    return None

def regs(d): return [(d[2*k] << 8) | d[2*k+1] for k in range(len(d)//2)]

def decode_fault(code):
    if code == 0: return "OK"
    hi = code >> 8
    if 0x41 <= hi <= 0x5A:
        return "%s%02d" % (chr(hi), code & 0xFF)
    return "0x%04X" % code

# etat partage, alimente au fil des trames
st = {}
st_lock = threading.Lock()

def update_from_frame(f):
    fc = f[1]
    out = {}
    if fc == 16 and len(f) > 8:                      # push FC10
        addr = (f[2] << 8) | f[3]; r = regs(f[7:7+f[6]])
        if addr == 0x07D0 and len(r) >= 7:           # bloc controle (aussi vu en lecture)
            out.update(ctrl_to_state(r))
        elif addr == 0x012C and len(r) >= 10:        # bloc capteurs (300)
            out.update(sensors_to_state(r))
        elif addr == 0x03E8 and len(r) >= 5:         # bloc eau/defaut (1000)
            out["t_inlet"] = round(r[2] / 10.0, 1)
            out["fault"] = decode_fault(r[4])
            out["fault_active"] = "ON" if r[4] != 0 else "OFF"
        elif addr == 0x0190 and len(r) >= 5:         # historique defauts (400)
            out["fault_history"] = [decode_fault(c) for c in r[1:5] if c]
    elif fc == 3 and len(f) > 5:                     # reponse lecture
        r = regs(f[3:3+f[2]])
        if f[2] == 14 and len(r) >= 7:               # 7 regs = bloc controle 0x07D0
            out.update(ctrl_to_state(r))
    if out:
        with st_lock:
            st.update(out)

def ctrl_to_state(r):
    return {
        "power":     "ON" if r[1] else "OFF",
        "mode":      MODES.get(r[0], "?"),
        "function":  FUNCS.get(r[2], "?"),
        "set_cool":  r[3],
        "set_heat":  r[4],
        "set_auto":  r[6],
    }

def sensors_to_state(r):
    return {
        "comp_freq":  r[0],
        "eev":        r[1],
        "t_ambient":  r[2],
        "t_outlet":   r[3],
        "t_discharge": r[4],
        "t_suction":  r[5],
        "t_coil_t3":  r[6],
        "t_4way":     r[7],
        "pump":       "ON" if r[8] else "OFF",
        "compressor": "ON" if r[0] > 0 else "OFF",
    }

# ---------------- definition des entites HA ----------------
# (component, key, Nom, unite, device_class, state_class, icon, extra)
ENTITIES = [
    ("binary_sensor", "power",       "Marche",                 None, "power",       None, "mdi:power",          {"payload_on": "ON", "payload_off": "OFF"}),
    ("sensor",        "mode",         "Mode",                   None, None,          None, "mdi:sync",           {}),
    ("sensor",        "function",     "Fonction",               None, None,          None, "mdi:tune",           {}),
    ("sensor",        "set_heat",     "Consigne chauffage",     "°C", "temperature", "measurement", None,        {}),
    ("sensor",        "set_cool",     "Consigne refroidissement","°C","temperature", "measurement", None,        {}),
    ("sensor",        "set_auto",     "Consigne auto",          "°C", "temperature", "measurement", None,        {}),
    ("sensor",        "t_inlet",      "Temp. entree eau",       "°C", "temperature", "measurement", None,        {}),
    ("sensor",        "t_outlet",     "Temp. sortie eau",       "°C", "temperature", "measurement", None,        {}),
    ("sensor",        "t_ambient",    "Temp. ambiante",         "°C", "temperature", "measurement", None,        {}),
    ("sensor",        "t_discharge",  "Temp. refoulement comp.","°C", "temperature", "measurement", None,        {}),
    ("sensor",        "t_suction",    "Temp. aspiration",       "°C", "temperature", "measurement", None,        {}),
    ("sensor",        "t_coil_t3",    "Temp. batterie (T3)",    "°C", "temperature", "measurement", None,        {}),
    ("sensor",        "t_4way",       "Temp. vanne 4 voies",    "°C", "temperature", "measurement", None,        {}),
    ("sensor",        "comp_freq",    "Frequence compresseur",  "Hz", "frequency",   "measurement", "mdi:sine-wave", {}),
    ("sensor",        "eev",          "Ouverture EEV",          "pas", None,         "measurement", "mdi:valve",  {}),
    ("binary_sensor", "pump",         "Pompe circulation",      None, "running",     None, "mdi:pump",           {"payload_on": "ON", "payload_off": "OFF"}),
    ("binary_sensor", "compressor",   "Compresseur",            None, "running",     None, "mdi:hvac",           {"payload_on": "ON", "payload_off": "OFF"}),
    ("sensor",        "fault",        "Code defaut",            None, None,          None, "mdi:alert-circle",   {}),
    ("binary_sensor", "fault_active", "Defaut actif",           None, "problem",     None, None,                 {"payload_on": "ON", "payload_off": "OFF"}),
]

DEVICE = {
    "identifiers": [DEVICE_ID],
    "name": DEVICE_NAME,
    "manufacturer": "AXEN (OEM) - POWER S INV",
    "model": "PAC piscine DC Inverter (RS485 Modbus via EW11)",
}

def publish_discovery(client):
    for comp, key, name, unit, dclass, sclass, icon, extra in ENTITIES:
        cfg = {
            "name": name,
            "unique_id": f"{DEVICE_ID}_{key}",
            "object_id": f"{DEVICE_ID}_{key}",
            "state_topic": STATE_TOPIC,
            "value_template": "{{ value_json.%s }}" % key,
            "availability_topic": AVAIL_TOPIC,
            "device": DEVICE,
        }
        if unit:   cfg["unit_of_measurement"] = unit
        if dclass: cfg["device_class"] = dclass
        if sclass: cfg["state_class"] = sclass
        if icon:   cfg["icon"] = icon
        cfg.update(extra)
        topic = f"{DISC_PREFIX}/{comp}/{DEVICE_ID}/{key}/config"
        client.publish(topic, json.dumps(cfg), qos=1, retain=True)
    print("[MQTT] auto-decouverte publiee (%d entites)" % len(ENTITIES))

# ---------------- boucle de lecture du bus ----------------
def reader_loop():
    while True:
        try:
            s = socket.socket(); s.settimeout(5); s.connect((EW11_HOST, EW11_PORT)); s.settimeout(1.0)
            print("[EW11] connecte a %s:%d" % (EW11_HOST, EW11_PORT))
            buf = bytearray()
            while True:
                try:
                    d = s.recv(4096)
                    if not d: raise ConnectionError("EW11 a ferme")
                    buf += d
                except socket.timeout:
                    continue
                i = 0; consumed = 0
                while i < len(buf):
                    f = next_frame(buf, i)
                    if not f: i += 1; continue
                    update_from_frame(bytes(f))
                    i += len(f); consumed = i
                if consumed: buf = buf[consumed:]
                if len(buf) > 8192: buf = buf[-2048:]   # garde-fou
        except Exception as e:
            print("[EW11] erreur: %s -> reconnexion 5s" % e)
            try: s.close()
            except: pass
            time.sleep(5)

# ---------------- MQTT ----------------
def main():
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("ERREUR: installe paho-mqtt :  pip install paho-mqtt"); sys.exit(1)

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="pac_bridge")
    except (AttributeError, TypeError):
        client = mqtt.Client(client_id="pac_bridge")

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.will_set(AVAIL_TOPIC, "offline", qos=1, retain=True)

    def on_connect(c, u, flags, rc, *a):
        print("[MQTT] connecte (rc=%s)" % rc)
        c.publish(AVAIL_TOPIC, "online", qos=1, retain=True)
        publish_discovery(c)
    client.on_connect = on_connect

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    threading.Thread(target=reader_loop, daemon=True).start()

    while True:
        time.sleep(PUBLISH_EVERY)
        with st_lock:
            snap = dict(st)
        if "t_inlet" in snap and "t_outlet" in snap:
            snap["water_delta"] = round(snap["t_outlet"] - snap["t_inlet"], 1)
        if snap:
            client.publish(STATE_TOPIC, json.dumps(snap), qos=0, retain=True)
            print("[MQTT] etat publie: %s" % json.dumps(snap, ensure_ascii=False))
        else:
            print("[MQTT] pas encore de donnees du bus...")

def selftest(secs=18):
    print("=== MODE TEST (sans MQTT) : ecoute %ds et affiche tout ce qui est decode ===" % secs)
    threading.Thread(target=reader_loop, daemon=True).start()
    t0 = time.time()
    while time.time() - t0 < secs:
        time.sleep(2)
        with st_lock:
            snap = dict(st)
        if "t_inlet" in snap and "t_outlet" in snap:
            snap["water_delta"] = round(snap["t_outlet"] - snap["t_inlet"], 1)
        print("  etat partiel: %s" % json.dumps(snap, ensure_ascii=False))
    with st_lock:
        snap = dict(st)
    if "t_inlet" in snap and "t_outlet" in snap:
        snap["water_delta"] = round(snap["t_outlet"] - snap["t_inlet"], 1)
    print("\n=== ETAT FINAL COMPLET (%d parametres) ===" % len(snap))
    for k in sorted(snap):
        print("  %-14s = %s" % (k, snap[k]))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        selftest()
    else:
        main()
