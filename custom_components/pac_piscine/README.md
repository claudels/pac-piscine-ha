# PAC Piscine — intégration native Home Assistant

Intégration **native** (custom component) qui lit la PAC de piscine sur son bus
RS485 (Modbus RTU) via une passerelle **EW11 en mode transparent (TCP server)**.
**Aucun broker MQTT, aucun script externe** : tout tourne dans Home Assistant.

Lecture seule (monitoring complet). Type : `local_push` (temps réel).

## Installation

1. Copie le dossier `pac_piscine/` dans le dossier `custom_components/` de ta
   config Home Assistant :
   ```
   <config>/custom_components/pac_piscine/
   ```
   (Sur HA OS : via l'add-on **Samba** ou **File editor / Studio Code Server**.)

2. **Redémarre Home Assistant** (Paramètres → Système → Redémarrer).

3. **Paramètres → Appareils et services → Ajouter une intégration** →
   cherche **« PAC Piscine »**.

4. Renseigne l'**IP de l'EW11** (def. `192.168.1.150`) et le **port** (def. `8899`).
   → L'appareil **« PAC Piscine »** apparaît avec toutes ses entités.

## Pré-requis EW11
- Mode **TCP Server**, port **8899**
- Série **RS485, 9600, 8, None, 1**
- **Protocol = None** (transparent)

## Entités créées
Marche, Mode, Fonction, 3 consignes, températures (entrée/sortie eau, delta,
ambiante, refoulement, aspiration, T3, vanne 4 voies), fréquence compresseur,
ouverture EEV, pompe, compresseur, code défaut (+ historique en attribut).

## Limites
- **Lecture seule** : changer mode/consigne depuis HA n'est pas encore possible
  (l'écriture sur ce bus nécessite d'émuler le module en temps réel — voir le
  document de protocole). Le monitoring, lui, est complet.

## Crédits
Basé sur la rétro-ingénierie de l'app DOTELS/AXEN et de la passerelle EW11.
Travaux connexes : [thomaswitt/poolpump](https://github.com/thomaswitt/poolpump).
