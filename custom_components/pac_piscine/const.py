"""Constantes et carte des registres pour l'integration PAC Piscine."""
from __future__ import annotations

DOMAIN = "pac_piscine"
DEFAULT_HOST = "192.168.1.150"
DEFAULT_PORT = 8899

CONF_HOST = "host"
CONF_PORT = "port"

MODES = {1: "Froid", 2: "Chaud", 4: "Auto"}
FUNCS = {0: "Smart", 0x10: "Silence", 0x400: "Boost"}

# Capteurs : (key, nom, unite, device_class, state_class, icon)
SENSORS = [
    ("mode",        "Mode",                     None, None,          None,          "mdi:sync"),
    ("function",    "Fonction",                 None, None,          None,          "mdi:tune"),
    ("set_heat",    "Consigne chauffage",       "°C", "temperature", "measurement", None),
    ("set_cool",    "Consigne refroidissement", "°C", "temperature", "measurement", None),
    ("set_auto",    "Consigne auto",            "°C", "temperature", "measurement", None),
    ("t_inlet",     "Temp. entrée eau",         "°C", "temperature", "measurement", None),
    ("t_outlet",    "Temp. sortie eau",         "°C", "temperature", "measurement", None),
    ("water_delta", "Delta eau",                "°C", "temperature", "measurement", "mdi:delta"),
    ("t_ambient",   "Temp. ambiante",           "°C", "temperature", "measurement", None),
    ("t_discharge", "Temp. refoulement comp.",  "°C", "temperature", "measurement", None),
    ("t_suction",   "Temp. aspiration",         "°C", "temperature", "measurement", None),
    ("t_coil_t3",   "Temp. batterie (T3)",      "°C", "temperature", "measurement", None),
    ("t_4way",      "Temp. vanne 4 voies",      "°C", "temperature", "measurement", None),
    ("comp_freq",   "Fréquence compresseur",    "Hz", "frequency",   "measurement", "mdi:sine-wave"),
    ("eev",         "Ouverture EEV",            "pas", None,         "measurement", "mdi:valve"),
    ("fault",       "Code défaut",              None, None,          None,          "mdi:alert-circle"),
]

# Capteurs binaires : (key, nom, device_class, icon)
BINARY_SENSORS = [
    ("power",        "Marche",            "power",   "mdi:power"),
    ("pump",         "Pompe circulation", "running", "mdi:pump"),
    ("compressor",   "Compresseur",       "running", "mdi:hvac"),
    ("fault_active", "Défaut actif",      "problem", None),
]
