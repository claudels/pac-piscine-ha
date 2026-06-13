# PAC Piscine — Home Assistant (EW11 / Modbus RTU)

Intégration **Home Assistant** (lecture/monitoring) pour les **pompes à chaleur de
piscine DC Inverter** d'OEM **AXEN** (revendues sous **POWER S**, Power Loop,
AcquaSource, Mundoclima, Thermway, Powerpool, Proteam, AES…), pilotées d'origine
par l'app **« Pool Panel » / DOTELS** et un module WiFi **HF-LPB130**.

Le principe : on remplace/double le module WiFi par une passerelle **EW11**
(RS485 ↔ WiFi, mode transparent) qui expose le bus **Modbus RTU** de la PAC, et
on décode tous les paramètres localement — **sans cloud**.

> ⚠️ **Lecture seule** pour l'instant (monitoring complet). Le pilotage (écriture)
> nécessite d'émuler le module en temps réel sur le bus — voir [docs/PROTOCOLE.md](docs/PROTOCOLE.md).

## Deux façons de l'utiliser

### 1. Intégration native (recommandé) — `custom_components/pac_piscine/`
Tourne **dans Home Assistant**, configuration par interface graphique, **sans
broker MQTT ni machine externe**. Compatible **HACS**.

- Copier `custom_components/pac_piscine/` dans `<config>/custom_components/`
  (ou via HACS → dépôt personnalisé), **redémarrer HA**, puis
  **Ajouter une intégration → « PAC Piscine »** → saisir l'IP de l'EW11.

### 2. Pont MQTT (alternative) — `mqtt_bridge/`
Script Python autonome → MQTT avec auto-découverte HA. Pratique si tu préfères
ne pas installer de custom component. Voir [mqtt_bridge/README.md](mqtt_bridge/README.md).

## Pré-requis EW11
- **TCP Server**, port **8899**
- **RS485**, **9600 / 8 / None / 1**
- **Protocol = None** (transparent)

## Entités exposées
Marche, mode (Froid/Chaud/Auto), fonction (Smart/Silence/Boost), 3 consignes,
températures (entrée eau, sortie eau, delta, ambiante, refoulement, aspiration,
batterie T3, vanne 4 voies), fréquence compresseur, ouverture EEV, pompe,
compresseur, code défaut (+ historique).

## Protocole
Tout est documenté dans [docs/PROTOCOLE.md](docs/PROTOCOLE.md) : carte des
registres (bloc contrôle `0x07D0`, capteurs `0x012C`, défaut `0x03E8`…),
encodage des fonctions et des codes défaut, etc.

## Crédits
Rétro-ingénierie de l'app DOTELS/AXEN et du bus EW11. Travaux connexes et
inspiration : [thomaswitt/poolpump](https://github.com/thomaswitt/poolpump).

## Licence
MIT — voir [LICENSE](LICENSE). Fourni sans garantie ; usage à tes risques
(interopérabilité avec ton propre matériel).
