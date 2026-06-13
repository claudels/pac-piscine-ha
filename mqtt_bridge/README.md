# Intégration Home Assistant — PAC piscine (POWER S / AXEN) via EW11

Pont **lecture seule** qui récupère **tous les paramètres** de la PAC sur le bus
RS485 (Modbus RTU) à travers une passerelle **EW11 en mode transparent**, et les
publie en **MQTT avec auto-découverte Home Assistant**. Toutes les entités
apparaissent automatiquement, regroupées sous l'appareil **« PAC Piscine »**.

Fichier : [`tools/pac_ha_bridge.py`](tools/pac_ha_bridge.py)

---

## 1. Prérequis

- Une machine **toujours allumée** sur le même réseau (Raspberry Pi, mini-PC, NAS, ou le PC HA lui-même).
- **Python 3** + la lib MQTT :
  ```bash
  pip install paho-mqtt
  ```
- Un **broker MQTT** (le plus simple : add-on **Mosquitto broker** dans Home Assistant) et l'**intégration MQTT** activée dans HA.
- La passerelle **EW11** configurée : **TCP Server**, port **8899**, **RS485**, **9600 8N1**, **Protocol = None (transparent)** — c'est ta config actuelle.

## 2. Configuration

Édite l'en-tête de [`tools/pac_ha_bridge.py`](tools/pac_ha_bridge.py) :

```python
EW11_HOST = "192.168.1.150"   # IP de l'EW11
MQTT_HOST = "192.168.1.10"    # IP de ton broker MQTT (souvent l'IP de Home Assistant)
MQTT_USER = "mqtt"            # identifiant MQTT (ou "" si anonyme)
MQTT_PASS = "motdepasse"      # mot de passe MQTT
```

## 3. Test rapide (sans MQTT)

Pour vérifier que la lecture du bus marche :
```bash
python tools/pac_ha_bridge.py test
```
Tu dois voir s'afficher l'état complet (mode, consignes, températures, etc.).

## 4. Lancement

```bash
python tools/pac_ha_bridge.py
```
À la connexion, le pont publie l'auto-découverte : ouvre Home Assistant →
**Paramètres → Appareils → « PAC Piscine »** : toutes les entités sont là.

## 5. Le faire tourner en permanence

**Linux (systemd)** — créer `/etc/systemd/system/pac-bridge.service` :
```ini
[Unit]
Description=Pont PAC piscine -> MQTT
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /chemin/vers/pac_ha_bridge.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now pac-bridge
```

**Windows** — Planificateur de tâches : déclencheur « Au démarrage », action
`python C:\...\pac_ha_bridge.py`, « Exécuter même si l'utilisateur n'est pas connecté ».

> Le pont se reconnecte tout seul si l'EW11 ou le broker tombe.

---

## 6. Entités créées dans Home Assistant

| Entité | Type | Unité | Registre source |
|---|---|---|---|
| Marche | binary_sensor | on/off | 2001 |
| Mode | sensor | Froid/Chaud/Auto | 2000 |
| Fonction | sensor | Smart/Silence/Boost | 2002 |
| Consigne chauffage | sensor | °C | 2004 |
| Consigne refroidissement | sensor | °C | 2003 |
| Consigne auto | sensor | °C | 2006 |
| Temp. entrée eau | sensor | °C | 1002 (÷10) |
| Temp. sortie eau | sensor | °C | 303 |
| Temp. ambiante | sensor | °C | 302 |
| Temp. refoulement compresseur | sensor | °C | 304 |
| Temp. aspiration | sensor | °C | 305 |
| Temp. batterie (T3) | sensor | °C | 306 |
| Temp. vanne 4 voies | sensor | °C | 307 |
| Fréquence compresseur | sensor | Hz | 300 |
| Ouverture EEV | sensor | pas | 301 |
| Pompe circulation | binary_sensor | on/off | 308 |
| Compresseur | binary_sensor | on/off | (freq > 0) |
| Code défaut | sensor | texte (P01…/OK) | 1004 |
| Défaut actif | binary_sensor | problème | 1004 |

Attribut bonus : `water_delta` (sortie − entrée) + l'historique des 5 derniers défauts.

---

## 7. Carte des registres (référence complète)

**Protocole : Modbus RTU, 9600 8N1.** Maître = carte PAC (`0xF0` = contrôleur filaire,
`0xE0` = afficheur, `0xFB` = slot module). Décodage par sniff passif.

### Bloc CONTRÔLE — `0x07D0` (2000), 7 registres
| Reg | Param | Valeurs |
|---|---|---|
| 2000 | mode | 1=Froid, 2=Chaud, 4=Auto |
| 2001 | marche | 0/1 |
| 2002 | fonction | 0=Smart, 0x10=Silence, 0x400=Boost |
| 2003 | consigne froid | °C (1:1) |
| 2004 | consigne chaud | °C (1:1) |
| 2005 | (inconnu, =45) | — |
| 2006 | consigne auto | °C (1:1) |

### Bloc CAPTEURS — `0x012C` (300), index = n° param − 1
| Reg | Param | Unité |
|---|---|---|
| 300 | fréquence compresseur | Hz |
| 301 | ouverture EEV | pas |
| 302 | température ambiante | °C |
| 303 | température sortie d'eau | °C |
| 304 | température de refoulement | °C |
| 305 | température d'aspiration | °C |
| 306 | température tuyauterie T3 | °C |
| 307 | température vanne 4 voies | °C |
| 308 | pompe de circulation | 0/1 |
| 309 | flag/état | 0/1 |

### Bloc EAU / DÉFAUT — `0x03E8` (1000)
| Reg | Param | Échelle |
|---|---|---|
| 1002 | température entrée d'eau | ÷10 |
| 1004 | **code défaut actif** | (lettre ASCII << 8) \| numéro — P01=0x5001 |

### Historique défauts — `0x0190` (400)
5 codes, même encodage ASCII (ex. P01, E24, E41, E01).

> Table des codes : P01 débit d'eau, P02 haute pression, P03 basse pression, P04 surchauffe T3,
> P05 haute T° refoulement, P06/P07 antigel, P08 haute pression 2 ; E01 comm contrôleur,
> E02–E09 capteurs, E10 comm PCB, E15/E16 bus DC, E17 surintensité, E18 IPM, E19 PFC, etc.

---

## 8. Et la commande (pilotage) ?

Pour l'instant **lecture seule**. L'écriture (changer mode/consigne) nécessite
d'« émuler le module » en répondant en temps réel sur le bus (registre de commande
`FC06`/unité `0x81`), ce que l'EW11+WiFi ne fait pas de façon fiable (latence).
Piste retenue : capturer la trame de commande exacte (en re-sniffant le module
d'origine pendant une commande via l'app), puis la rejouer depuis un ESP32 câblé.
Le monitoring, lui, est complet et fiable.
