# Spécification technique — Boîtier de remplacement du module WiFi sur le bus RS485 d'une PAC de piscine

**Cible :** PAC de piscine « POWER S … INV » (Super DC Inverter, R32, compresseur rotatif Toshiba), carte de commande dialoguant en RS485 / Modbus RTU, module WiFi d'origine = **Hi‑Flying HF‑LPB130** (classe HF‑LPB100 / HF‑A11).

**Source :** décompilation de l'APK `dotels.apk` (package `com.heatpump`, jadx) + notice PDF `notice-pac-powerloop-fr-couleur-blanche-34650.pdf`.

**Objectif :** construire un boîtier maison qui se substitue au module WiFi sur le RS485 et parle le **même** protocole que le contrôleur PAC, soit en pilotant directement le contrôleur (**Option A**), soit en émulant le module / le côté cloud (**Option B**).

---

## ⚠️ Avertissement méthodologique — à lire en premier

Toutes les analyses proviennent de la décompilation de l'app Android et de la notice. **Point capital, confirmé de façon exhaustive (grep sur tout l'arbre source) : l'application ne construit JAMAIS de trame Modbus, ni de CRC, ni de code de fonction.** Elle envoie au cloud (`http://www.fzdbiology.com:8080`) des tuples `{code, value, addr, rtuCode}` en clair par HTTP. C'est le **cloud** qui traduit `{addr, value}` en trame Modbus RTU et la pousse via un tunnel TCP transparent (port 502) vers le module WiFi, qui la relaie verbatim sur le RS485.

**Conséquences directes :**
- Les **adresses des registres d'ÉCRITURE (2000–2006) sont connues et fiables** (constantes de l'app, `APIContext.java`).
- En revanche, **le format exact de la trame Modbus (code fonction, slave ID, baud, parité, scaling final, adresses des registres de LECTURE) n'est PAS déterminable depuis la décompilation** et **doit être confirmé par sniffing**. Voir la section [§8 « À CONFIRMER PAR SNIFFING »](#8-à-confirmer-par-sniffing).

---

## 0. ✅ CONFIRMÉ EN DIRECT SUR LE BUS (capture EW11, 9600 8N1)

Vérifié par sniffing Modbus réel via la passerelle Elfin‑EW11 (RS485 ↔ TCP server 8899) :

- **Ligne série : 9600 8N1** — confirmé (toutes les trames à CRC valide).
- **Protocole : Modbus RTU.** Un **maître natif (contrôleur filaire) pilote déjà le bus.** Nœuds vus : `0xF0` (carte principale), `0xE0` (afficheur), `0xFB`, `0xF1`. Codes fonction : `0x03` (read holding), `0x04` (read input), `0x10` (write multiple).
- **Bloc de contrôle `0x07D0` (=2000) CONFIRMÉ**, lu sur `0xF0` et écrit sur `0xFB`. Scaling **1:1** (consigne 27 °C = registre = 27).
- **Registre 2002 `function` = champ de bits NATIF** (≠ valeurs 1/2/4 de l'app), décodé par bascule réelle :

| Mode | Registre 2002 |
|---|---|
| **Smart** | `0x0000` |
| **Silence** | `0x0010` (bit 4) |
| **Boost** | `0x0400` (bit 10) |

- État live confirmé : `0x07D0 = [model=2 Chaud, switch=1 ON, function, cooltemp=12, heattemp=27, reg2005=45, autotemp=27]`.

### Bloc CAPTEURS confirmé : `0x012C` (registre 300), lu sur `0xF0`, scaling 1:1

Validé en corrélant la capture avec l'écran « requête de paramètre » du contrôleur (correspondance parfaite). **Registre = 300 + (n° paramètre − 1)** :

| Registre | Index | Paramètre | Unité | Vérif écran |
|---|---|---|---|---|
| **300** | [0] | Fréquence compresseur | Hz | 100 ✓ |
| **301** | [1] | Ouverture EEV | pas | 44 ✓ |
| **302** | [2] | Température ambiante | °C | 19 ✓ |
| **303** | [3] | Température sortie d'eau | °C | 23 ✓ |
| **304** | [4] | Température de décharge | °C | 90 ✓ |
| **305** | [5] | Température d'aspiration | °C | 5 ✓ |
| **306** | [6] | Température tuyauterie T3 | °C | 10 ✓ |
| **307** | [7] | Temp. sortie vanne 4 voies | °C | 23 ✓ |
| **308** | [8] | Pompe de circulation | 0/1 | 1 ✓ |
| **309** | [9] | État vanne 4 voies / flag | 0/1 | 1 ✓ |
| 310–311 | [10–11] | réservé | — | 0 |

> Lecture recommandée pour la domotique : `FC 0x03`, esclave `0xF0`, adresse `0x012C` (300), quantité 12. Toutes les valeurs en **°C entiers (1:1)**, sauf la fréquence (Hz) et l'EEV (pas). Le bloc `0xE0 @0x1F40` (8000) contient les mêmes grandeurs formatées ×10 pour l'afficheur.

### Défauts (confirmé en provoquant un P01)

- **Défaut actif courant = registre 1004** (`0xF0 @0x03E8`, index 4) : `0x0000` = aucun, sinon code défaut.
- **Encodage du code = (lettre ASCII << 8) | numéro.** Ex. **P01 = `0x5001`** (`0x50`='P'), E01 = `0x4501`, E16 = `0x4510`, P02 = `0x5002`…
- **Historique des défauts = bloc `0xF0 @0x0190` (registre 400)** : liste de codes même encodage (observé `0x5001,0x4518,0x4529,0x4501` = P01, E24, E41, E01).
- Au déclenchement d'un défaut bloquant (P01) : `308` (pompe) → 0, `300` (fréq compresseur) → 0, flag marche `8000[10]` → 0 (la PAC coupe en protection).

> Table des codes (P01–P08, E01–E51) : voir §4.3. Pour décoder en clair : `lettre = chr(reg >> 8)`, `numéro = reg & 0xFF`.

### Source ouverte de référence : thomaswitt/poolpump (MÊME PAC OEM)

Le projet **[thomaswitt/poolpump](https://github.com/thomaswitt/poolpump)** documente **exactement** cette plateforme (OEM AXEN « DOTELS-SWP », module HF-LPB130, cloud fzdbiology). Confirme registre par registre notre bloc 2000-2006 et la fonction (Smart=0x0000/Silence=0x0010/Boost=0x0400). Donne en plus :
- Codecs capteurs : 315 courant moteur ÷10, 316 tension secteur ×10, 321 tension DC ×5, 322 courant DC, 1001 entrée eau ÷10 (0.1 °C).
- Mode (reg 2000) brut : **0x01=Froid, 0x02=Chaud, 0x04=Auto** — confirmé (= notre observation).
- **Dictionnaire complet des descriptions de défauts P01–E51** (réutilisable pour l'UI).
- ⭐ poolpump n'a **jamais** trouvé le registre de défaut actif (il a réfuté reg 500) → **notre reg 1004 = 0x5001 est le chaînon manquant, à leur contribuer.**

### PILOTAGE / ÉCRITURE — méthode confirmée (≠ bus du contrôleur)

**Architecture : deux interfaces série distinctes.**
1. **Bus contrôleur filaire** (ce que l'EW11 sniffe) : Modbus **RTU** (CRC), 9600 8N1, maître = carte principale, esclaves 0xF0/0xE0/0xFB. → parfait pour la **LECTURE**, mais les consignes y sont détenues par le contrôleur (lecture seule pour nous).
2. **Port du module WiFi** (là où le HF-LPB130 se branche) : Modbus **TCP / MBAP** (TID + unit ID, **sans CRC**). → c'est **LÀ qu'on écrit**.

**Protocole de commande sur le port module :**
- La PAC est cliente TCP et **pousse** la télémétrie en **FC 0x10** + heartbeat **FC 0x41**. Il faut **acquitter** chaque trame (sinon plus de télémétrie).
- Commander = envoyer des **FC 0x06 (mono-registre), unit ID `0x81`** (`0x01 | 0x80`). **Ne PAS utiliser FC 0x10** (refusé, ferme la session). Une trame par registre.
- La PAC renvoie un **écho FC 0x06** (~150 ms) = confirmation. Échec = exception FC 0x86.
- Consigne : écrire **0x07D4 (affichage)** ET **0x07D6 (consigne réelle)**.

> **Solution clé-en-main** : faire pointer le HF-LPB130 (ou l'EW11 en mode transparent placé sur le port module) vers un serveur poolpump (Docker fourni) → lecture + écriture + API REST immédiates, sans rien réécrire. Outil de reprovisionnement inclus (`reprovision.rb` : UDP 48899 + `AT+NETP="TCP,Client,<ip>,<port>"` + `AT+Z`).

> ⚠️ **Il y a déjà un maître sur le bus.** Pour **LIRE** → sniff passif (sûr, aucune collision). Pour **ÉCRIRE** → reproduire l'écriture du bloc `0x07D0` vers le nœud `0xFB` (comme le faisait le module/cloud), intercalée pour éviter les collisions.

---

## 1. Architecture globale (telle que décompilée)

```
   [App Android « Pool Panel »]
        |  HTTP clair (port 8080), Retrofit/OkHttp
        |  POST scadaiot/rtuModel/saveCode.do  {code,value,addr,rtuCode}
        |  GET  scadaiot/rtuModel/getRtuRealTime.do?rtuId=...
        v
   [Cloud SCADA  www.fzdbiology.com]
        |  <-- ICI : traduction {addr,value} -> trame Modbus RTU (FC + CRC16)
        |  TCP serveur, port 502 (port Modbus standard), octets transparents
        v
   [Module WiFi Hi-Flying HF-LPB130]   (client TCP transparent)
        |  pont transparent TCP:502  <->  UART/RS485
        |  aucun octet ajouté/retiré : passe-plat brut
        v
   [Contrôleur PAC]   bus RS485, Modbus RTU, alimentation DC12V
```

Points structurants **vérifiés** :

- **Le module est un pont série↔WiFi transparent.** Provisionné, il ouvre une connexion TCP **cliente** vers `www.fzdbiology.com:502` et relaie les octets verbatim entre ce socket et l'UART/RS485 (aucun CRC ni cadrage ajouté côté module ou app).
- **L'app a deux rôles seulement :** (1) provisionneur du module via commandes AT‑over‑UDP, (2) client REST HTTP vers le cloud. Toute la logique Modbus est **côté serveur**.
- **La télémétrie n'est PAS lue en direct par l'app.** L'app interroge le snapshot mis en cache par le cloud (`getRtuRealTime.do`). Le polling Modbus réel de la PAC est fait par le cloud.
- **Port 8080 (HTTP app)** et **port 502 (tunnel Modbus transparent)** partagent le même DNS `www.fzdbiology.com` mais sont deux canaux distincts. (Notice : ancien hôte legacy `47.254.152.109`.)
- **Les classes de pont transparent dans l'app (`TransparentTransmission`, `TCPClient`) sont du code mort** : jamais instanciées au runtime. Le pont est entièrement résident dans le module.

**Implication pour le boîtier maison : aucun exemple de trame Modbus réelle n'existe dans le code.** Le mapping registre→fonction Modbus est une **hypothèse de départ** à valider sur le bus.

---

## 2. Paramètres de la ligne série RS485 (connu vs à confirmer)

| Paramètre | Valeur | Statut |
|---|---|---|
| Support physique | RS485 (paire différentielle A/B) | **CONNU** (notice §6.1 : « Communication RS485 ») |
| Alimentation contrôleur / bus filaire | DC 12 V | **CONNU** (notice §6.1 : « Tension d'entrée: DC12V ») |
| Protocole applicatif | Modbus RTU | **FORTEMENT PRÉSUMÉ** (port 502 = Modbus standard ; adresses holding 2000–2006 ; cloud = traducteur Modbus). Non prouvé octet par octet. |
| Débit (baud) | **9600 présumé** (défaut usuel HF‑LPB100) | **À CONFIRMER** — absent de la notice et de l'app |
| Bits / parité / stop | **8N1 présumé** | **À CONFIRMER** |
| Slave ID (adresse esclave) | inconnu (souvent 1) | **À CONFIRMER** |
| FC écriture | 0x06 (Write Single) ou 0x10 (Write Multiple) | **À CONFIRMER** |
| FC lecture | 0x03 (Read Holding) ou 0x04 (Read Input) | **À CONFIRMER** |
| Adresses registres de LECTURE | inconnues (l'app lit du JSON, pas des registres) | **À CONFIRMER** |
| Scaling final sur le fil | présumé 1:1 (voir §3 note) | **À CONFIRMER** |

> **Câblage (notice, schéma p.20) :** le bornier `L N (gnd) P1 P2` = alimentation + sortie pompe (**P1/P2 = « To pump », PAS le RS485**). Le bornier `1 2` (RED/BLK) = entrée ON/OFF externe. **Le RS485 transite par le faisceau du contrôleur filaire / module WiFi (bus « Wire Controller » qui porte RS485 + DC12V), pas par P1/P2.** Repérez physiquement la paire A/B au sniffing. Transceiver **isolé recommandé** (ADM2483 / MAX14483) ; ne tirez pas le 12 V du bus sans vérifier la charge admissible ; communisez les masses.

---

## 3. Carte des registres d'ÉCRITURE (2000–2006) — CONNUS

Adresses et sémantiques = constantes de l'app (`APIContext.java`), passées au cloud comme paramètre `addr`. **Scaling côté app = 1:1 ; aucune multiplication/division dans le code.**

| Reg (déc) | Reg (hex) | Clé (`code`) | Signification | Plage | Valeurs / énum |
|---|---|---|---|---|---|
| **2000** | 0x07D0 | `model` | Mode (Froid / Chaud / Auto) | énum {1,2,4} | **1 = Froid**, **2 = Chaud**, **4 = Auto** |
| **2001** | 0x07D1 | `switch` | Marche/Arrêt | 0..1 | **0 = OFF**, **1 = ON** |
| **2002** | 0x07D2 | `function` | Profil (Silence/Boost/Smart) — **valeur unique, PAS un masque** | énum {1,2,4} | **1 = Silence**, **2 = Boost**, **4 = Smart** |
| **2003** | 0x07D3 | `cooltemp` | Consigne Froid (°C) — si `model==1` | **8..25 °C** (pas 1) | consigne entière |
| **2004** | 0x07D4 | `heattemp` | Consigne Chaud (°C) — si `model==2` | **15..40 °C** (pas 1) | consigne entière |
| **2005** | — | — | **non défini / inutilisé** (trou volontaire) | — | — |
| **2006** | 0x07D6 | `autotemp` | Consigne Auto (°C) — si `model==4` | **8..40 °C** (pas 1) | consigne entière |

### Règles métier d'écriture (vérifiées dans `MainDeviceFragment`)

- **Une seule consigne écrite par action**, selon le mode courant : `model==1`→2003 ; `model==2`→2004 ; `model==4`→2006.
- **`function` (2002) n'est pas un masque** : RadioGroup mutuellement exclusif ; la valeur est exactement un de {1,2,4}, jamais une somme. (En lecture, le statut est reconstitué via deux booléens `silence` et `boost` ; « smart » = aucun des deux.)
- **`switch` (2001)** = bascule : l'app lit l'état et écrit l'inverse.
- **Offsets UI** (curseur → valeur envoyée) : Froid `progress+8`, Chaud `progress+15`, Auto `progress+8`. La valeur transmise est déjà la température en °C (ex. 40 → valeur 40).

> **Attention au scaling final :** l'app envoie l'entier brut (40 °C → 40), mais **c'est le cloud qui encode la trame finale** ; il pourrait appliquer un ×10 (registre = 400) comme de nombreuses PAC. La valeur *sur le fil RS485* est **À CONFIRMER** (§8). Indice fort : la notice donne des scalings explicites en lecture (« courant ×10 », « tension /10 », « ventilateur /10 », « EEV /5 »), donc des facteurs ×10/÷10/÷5 existent bien sur ce contrôleur.

---

## 4. Registres de LECTURE / télémétrie — sémantique CONNUE, adresses INCONNUES

> **Critique :** l'app ne lit jamais de registres Modbus ; elle reçoit du JSON depuis le cloud (`getRtuRealTime.do`), aux étiquettes vendeur (`ap*`/`pa*`/`pb*`) qui **ne sont pas des adresses**. **Les adresses Modbus de lecture sont inconnues et doivent être trouvées au sniffing.** Le tableau donne la sémantique (pour reconnaître les valeurs) et les indices de mapping de la notice.

### 4.1 Champs de télémétrie exploités par l'app (JSON)

| Clé JSON | Signification | Unité | Échelle (app) | Type | Affiché ? |
|---|---|---|---|---|---|
| `ap2` | Température ambiante (air extérieur) | °C | brut | double | Oui |
| `ap3` | Température d'eau **sortie** | °C | brut | double | Oui |
| `pa10` | Température d'eau **entrée** (retour) — « water temp » | °C | brut | double | Oui |
| `pa13` | **Code défaut courant** (« Unit malfuntion », sic) | code/texte | verbatim | string | Oui |
| `pa15` | Taux de charge compresseur | % | brut + suffixe « % » | string | Oui |
| `pb11` | État de fonctionnement (运行状态) | code/texte | brut | string | **Non** (décodé, jamais affiché) |
| `switchs` | État ON/OFF | bool | 0=OFF, ≠0=ON | int | icône |
| `model` | Mode courant | énum | 1/2/4 | int | icône |
| `boost` | Boost actif | bool | `==1` | int | icône |
| `silence` | Silence actif | bool | `==1` | int | icône |
| `cooltemp`/`heattemp`/`autotemp` | Consignes (mêmes clés qu'en écriture) | °C | brut | int | curseur |
| `ap0,ap1,ap4..ap26` | Télémétrie brute **non étiquetée, jamais affichée** | inconnu | n/a | string | Non |

> Côté lecture il n'y a **pas** de champ `function` ; le profil courant est reconstruit depuis `boost` + `silence`.

### 4.2 Liste de paramètres lecture-seule de la notice (codes 1–21) → scalings réels

Suggère un mapping type Phnix/JLNTECH et fournit les **facteurs d'échelle** à attendre sur le bus :

| Code notice | Paramètre | Scaling notice |
|---|---|---|
| 1 | Fréquence compresseur (Hz) | brut |
| 2 | Angle ouverture EEV | **/5** |
| 3 | Température ambiante (°C) | brut → corrèle `ap2` |
| 4 | Température sortie d'eau (°C) | brut → corrèle `ap3` |
| 5 | Température de décharge (°C) | brut |
| 6 | Température aspiration (°C) | brut |
| 7 | Température tuyauterie T3 (°C) | brut |
| 8 | Température sortie vanne 4 voies (°C) | brut |
| 9 | Pompe circulation eau | 0/1 |
| 10 | Défaut vanne 4 voies | 0/1 |
| 16 | Courant compresseur | **×10** |
| 17 | Tension | **/10** |
| 21 | Vitesse ventilateur | **/10** |

> Ces facteurs **prouvent que le contrôleur utilise des scalings**. Attendez‑vous à devoir les appliquer sur les registres de lecture (et possiblement ×10 sur les consignes de température). La notice ne donne **aucune adresse Modbus** ni le débit.
>
> **DIP switch SW1 (modèle d'usine)** : OFF/OFF = Multifonction, OFF/ON = Piscine, ON/OFF = Eau froid+chaud, ON/ON = Chauffage maison.

### 4.3 Codes de panne (notice — pour décoder `pa13` et le bus)

**Protections P :** P01 débit d'eau · P02 haute pression · P03 basse pression · P04 surchauffe batterie T3 · P05 haute T° décharge · P06 antigel eau sortie · P07 antigel tuyauterie · P08 haute pression 2.

**Erreurs E (sélection) :** E01 comm. contrôleur (câble coupé) · E02 capteur décharge TP1 · E03 capteur tuyauterie T3 · E04 capteur ambiant T4 · E05 capteur gaz liquide T5 · E06 capteur gaz retour TH · E07 capteur batterie TW · E08 capteur eau entrée Tin · E09 capteur eau sortie T7 · E10 comm. carte↔PCB drive · E15 bus DC trop bas · E16 bus DC trop haut · E17 surintensité AC · E18 IPM · E19 PFC · E20 démarrage compresseur · E21 phase compresseur manquante · E23 surintensité compresseur · E28 erreur comm. · E29/E30 IPM surchauffe/capteur · E51 comm. moteur ventilateur.

---

## 5. Provisionnement et protocole AT du module WiFi (CONNU)

Éléments **vérifiés verbatim** — utiles pour (a) reconfigurer le module original vers VOTRE serveur (Option B), (b) émuler le côté module.

### 5.1 Découverte (UDP)

| Élément | Valeur |
|---|---|
| Chaîne magique | `HF-A11ASSISTHREAD` (ASCII) |
| Port UDP | **48899** |
| Transport | broadcast UDP → `255.255.255.255:48899` ; réponse module sur le même port |
| Format réponse | ASCII CSV : `ip,mac[,moduleID]` ; mac = 12 hex contigus |
| Préconditions app | téléphone joint au SoftAP `HF-LPB130` + GPS/localisation activés |

### 5.2 Commandes AT (terminateur = CR `\r`/0x0D ; succès = `+ok`, parfois suivi de `\r\n\r\n`)

| Constante | Littéral exact | Rôle |
|---|---|---|
| CMD_TEST | `AT+\r` | Entrer / sonder le mode commande |
| (handshake) | `+ok` | Jeton de confirmation d'entrée mode commande |
| CMD_SET_SSID | `AT+WSSSID=<SSID>\r` | SSID routeur cible (mode STA) |
| CMD_SET_PSW | `AT+WSKEY=WPA2PSK,AES,<pwd>\r` | Sécurité WLAN WPA2PSK/AES + mot de passe |
| CMD_SET_PSW_WITHOUT_PSW | `AT+WSKEY=OPEN,NONE\r` | WLAN ouvert (sans mot de passe) |
| **CMD_SET_HOST** | `AT+NETP=TCP,CLIENT,502,www.fzdbiology.com\r` | **Cible runtime : client TCP vers hôte:502 — À MODIFIER pour pointer vers VOTRE serveur (Option B)** |
| CMD_SET_STA | `AT+WMODE=STA\r` | Passage en mode Station |
| CMD_RESET | `AT+Z\r` | Reboot (applique la config) |
| CMD_NETWORK_PROTOCOL | `AT+NETP\r` | Lecture config réseau (réponse `+ok=...`) |
| CMD_TRANSPARENT_TRANSMISSION | `AT+ENTM\r` | Entrée en transmission transparente |
| CMD_EXIT_CMD_MODE | `AT+Q\r` | Quitter le mode commande |
| CMD_RELOAD | `AT+RELD\r` | Restauration usine (réponse `+ok=rebooting`) |

### 5.3 Séquence de provisionnement (chaque étape déclenchée par réception de `+ok\r\n\r\n`, ~1000 ms entre étapes)

```
enterCMDMode (AT+\r, fallback : magic + "+ok")
  -> AT+WSSSID=<SSID>\r
  -> AT+WSKEY=WPA2PSK,AES,<pwd>\r      (ou AT+WSKEY=OPEN,NONE\r)
  -> AT+NETP=TCP,CLIENT,502,www.fzdbiology.com\r
  -> AT+WMODE=STA\r
  -> AT+Z\r   (reboot ; repart hors mode commande en client TCP transparent)
```

> Le pairing **n'utilise pas** `AT+ENTM` : après `AT+Z`, le module redémarre directement en client TCP transparent. `AT+ENTM` n'est utilisé que par un chemin alternatif (`exitCMDMode`) non emprunté au pairing.

---

## 6. Deux options d'intégration pour le boîtier maison

### Option A — Émuler le côté PAC : boîtier = nœud Modbus direct sur RS485  *(recommandée)*

**Principe :** débrancher le module WiFi, brancher votre boîtier (ESP32/RPi + transceiver RS485 isolé) sur la paire A/B du bus contrôleur, et parler Modbus RTU directement.

**Avantages :** autonomie totale, zéro cloud, latence minimale.

**À implémenter :**
1. **Matériel :** transceiver RS485 isolé (ADM2483/MAX14483), alim séparée, masses communes, résistance de terminaison 120 Ω si besoin.
2. **Série :** démarrer à **9600 8N1**, slave ID **1** (hypothèses) — à valider.
3. **Écritures :** **FC 0x06** vers 2000, 2001, 2002, et 2003/2004/2006 selon le mode (énums/plages §3).
4. **Lectures :** **FC 0x03** (ou 0x04) sur la plage à découvrir au sniffing.
5. Respecter les règles métier §3 (une consigne par mode, function = valeur unique…).
6. Appliquer le scaling final déterminé au sniffing (probable ×10 sur certaines températures, ÷10/÷5 sur capteurs).

> **⚠️ Sens du polling — premier point à trancher.** Deux cas :
> - **Variante A (maître) :** si c'est le module/cloud qui interroge la PAC, alors la PAC est esclave → votre boîtier prend le rôle **maître**.
> - **Variante A′ (esclave) :** si le contrôleur PAC est maître et interroge le module, votre boîtier doit **répondre comme esclave**.
>
> **Ne prenez pas le bus avant d'avoir observé qui parle/répond (§8.2 Méthode 1).** Risque de collision sinon (surtout si un contrôleur filaire est aussi présent).

### Option B — Émuler le côté module / cloud : boîtier = serveur TCP du module

**Principe :** garder le module Hi‑Flying sur le RS485, mais le reconfigurer (AT §5) pour qu'il pointe vers **votre** serveur au lieu de `www.fzdbiology.com:502`.

**À implémenter :**
1. Rejoindre le SoftAP `HF-LPB130`, envoyer (UDP 48899) la séquence AT §5.3 en remplaçant `CMD_SET_HOST` par `AT+NETP=TCP,CLIENT,502,<IP_de_votre_serveur>\r`, puis `AT+WMODE=STA`, `AT+Z`.
2. Faire tourner un **serveur TCP** sur le port choisi ; le module s'y connecte en client.
3. Sur ce socket, échanger des **trames Modbus RTU brutes** (le module est passe‑plat) → c'est votre serveur qui construit les trames (FC + CRC16), comme le faisait le cloud.

**Avantage :** aucun câblage RS485, réutilise le module. **Inconvénient :** dépendance module + WiFi, latence, et le format de trame reste à connaître (le sniffing reste nécessaire).

**Sous‑variante :** réutiliser l'app Android d'origine impose aussi d'émuler l'API REST (§7) — beaucoup plus de travail. Pour un boîtier maison, l'Option A ou « B serveur TCP brut » est plus simple.

---

## 7. API cloud REST (référence — pour la variante « émuler le cloud »)

Base : `http://www.fzdbiology.com:8080`, chemins préfixés `scadaiot/`. Auth par en‑têtes `userId` + `token`. HTTP **en clair** (pas de TLS), timeouts 60 s.

| Méthode | Chemin | Paramètres | Rôle |
|---|---|---|---|
| POST (form) | `scadaiot/rtuModel/saveCode.do` | `code`, `value`, `addr` (2000–2006), `rtuCode` | **Écriture de commande** (le cloud encode le Modbus) |
| GET | `scadaiot/rtuModel/getRtuRealTime.do` | `rtuId` | **Lecture télémétrie** (snapshot JSON caché) |
| GET | `scadaiot/rtuReal/getRtuFaultCode.do` | `rtuId`, `start`, `pageSize`(=20) | Journal de pannes paginé |
| GET | `scadaiot/rtuModel/getRtuView.do` | `userId` | Liste des PAC liées au compte |
| GET | `scadaiot/rtuModel/saveRtuIne.do` | `rtuCode`, `rtuName`, `userId`, `longitude`, `latitude` | Lier une PAC |
| GET | `scadaiot/rtuModel/removeRtuIne.do` | `rtuCode` | Délier une PAC |
| GET | `scadaiot/rtuModel/upRtuName.do` | `rtuName`, `rtuId` | Renommer |
| POST (form) | `scadaiot/user/loginUser.do` | `email`, `password` | Login (renvoie userId + token) |

> Nuance d'identifiant : les **écritures** utilisent `rtuCode` (String), les **lectures** utilisent `rtuId` (long). Le `rtuCode` correspond au MAC du module.

---

## 8. À CONFIRMER PAR SNIFFING

> Rien ici n'est prouvé par le code. **Ne câblez pas en aveugle.**

### 8.1 Liste des inconnues

1. **Sens du polling (qui est maître)** → détermine Variante A (maître) vs A′ (esclave). **À trancher en premier.**
2. **Débit (baud)** : 9600 présumé.
3. **Format série** : parité / data bits / stop (8N1 présumé).
4. **Slave ID**.
5. **Codes de fonction** : écriture 0x06 vs 0x10 ; lecture 0x03 vs 0x04.
6. **Adresses Modbus des registres de LECTURE** (les étiquettes `ap*/pa*` ne sont pas des adresses).
7. **Scaling final sur le fil** (consignes ×10 ? capteurs ÷10/÷5 ?).
8. **Confirmer que 2000–2006 sont bien les adresses Modbus réelles** (et pas un index applicatif remappé par le cloud).
9. **Endianness / registres 32 bits** (grandeurs sur 2 registres ?).

### 8.2 Méthodes de capture (par ordre de préférence)

**Méthode 1 — Sniffer passif sur le RS485 (le plus fiable).**
Laisser tout le système d'origine fonctionner et mettre **en parallèle** un adaptateur USB‑RS485 en **écoute seule** sur A/B.
- Outils : `mbpoll`/`modpoll` en écoute, ou un script `pyserial` enregistrant les octets bruts, ou un analyseur logique.
- Tester débits **9600, 19200, 4800, 38400** et parités N/E/O jusqu'à obtenir des trames Modbus **à CRC valide**.
- Depuis l'app, **déclencher des actions connues** (ON/OFF, changement de mode, consigne 30 °C en chauffage) : on voit alors les écritures des registres 2001/2000/2004. Cela **confirme directement** FC, slave ID, endianness et scaling (la valeur 30 apparaît‑elle `0x001E`=30 ou `0x012C`=300 → ×10 ?).
- Observer les trames de **lecture** (FC 0x03/0x04) du maître pour cartographier les adresses de télémétrie : corréler les valeurs lues avec `ap2/ap3/pa10/pa15` affichés dans l'app.

**Méthode 2 — Module original redirigé vers votre serveur TCP (capture côté tunnel).**
Reconfigurer le module (AT §5) : `AT+NETP=TCP,CLIENT,502,<votre_PC>`. Votre PC = serveur TCP : les octets relayés **sont exactement les trames Modbus RTU** du RS485 (module transparent). Capture sans toucher au câblage série, et possibilité de **rejouer** les trames pour valider.

**Méthode 3 — Sondage actif prudent (en dernier, après §8.1 point 1).**
Si la PAC est esclave : débrancher le module, brancher votre maître USB‑RS485, balayer en **lecture seule** (FC 0x03 autour de 2000–2006 et au‑delà), 9600 8N1, slave ID 1. **Ne jamais écrire en aveugle** : valider d'abord les lectures, puis tester une écriture neutre (relire le mode, le réécrire à l'identique).

---

## 9. Exemples de trames Modbus RTU — HYPOTHÈSE DE DÉPART (CRC16 vérifiés)

> **⚠️ HYPOTHÈSE :** ces trames supposent **slave ID = 0x01**, **FC écriture = 0x06**, **FC lecture = 0x03**, **scaling 1:1**, **registres 2000–2006 = adresses Modbus réelles**, **big‑endian Modbus standard**. Ces hypothèses **ne sont pas confirmées par la décompilation** — valider au sniffing (§8) avant usage.
>
> **Les CRC ci‑dessous ont été recalculés et vérifiés** (polynôme Modbus 0xA001, init 0xFFFF), transmis **little‑endian** (octet bas en premier). Recalculez‑les toujours dans votre code.

Rappel hex : 2000=`0x07D0`, 2001=`0x07D1`, 2002=`0x07D2`, 2004=`0x07D4`, 2006=`0x07D6`.

### 9.1 Écritures (FC 0x06, Write Single Register)

| Action | Payload (avant CRC) | CRC16 | **Trame complète** |
|---|---|---|---|
| **ON** (reg 2001 = 1) | `01 06 07 D1 00 01` | 0x4719 | `01 06 07 D1 00 01 19 47` |
| **OFF** (reg 2001 = 0) | `01 06 07 D1 00 00` | 0x87D8 | `01 06 07 D1 00 00 D8 87` |
| **Mode Chaud** (reg 2000 = 2) | `01 06 07 D0 00 02` | 0x8608 | `01 06 07 D0 00 02 08 86` |
| **Consigne chauffage 30 °C** (reg 2004 = 30) | `01 06 07 D4 00 1E` | 0x8E48 | `01 06 07 D4 00 1E 48 8E` |

Réponse attendue d'un esclave Modbus pour FC 0x06 = **écho exact** de la requête (8 octets identiques).

> Si au sniffing la consigne 30 °C apparaît comme `01 2C` (=300) au lieu de `00 1E` (=30), alors **scaling ×10** → envoyer 300, pas 30.

### 9.2 Lecture (FC 0x03, Read Holding Registers : 7 registres 2000→2006)

Requête — payload `01 03 07 D0 00 07`, CRC16 = **0x8504** → trame :
```
01 03 07 D0 00 07 04 85
```

Réponse attendue (7 registres = 14 octets de données) :
```
01 03 0E [r2000][r2001][r2002][r2003][r2004][r2005][r2006] [CRC_lo CRC_hi]
 |  |  |
 |  |  octet count = 0x0E (14)
 |  FC 0x03
 slave 0x01
```
Interprétation attendue (si 1:1) — ex. mode Chaud à 30 °C : r2000=`00 02`, r2001=`00 01`, r2002=`00 04`, r2004=`00 1E`.

### 9.3 Référence CRC16‑Modbus

```c
uint16_t crc16_modbus(const uint8_t *buf, int len) {
    uint16_t crc = 0xFFFF;
    for (int i = 0; i < len; i++) {
        crc ^= buf[i];
        for (int b = 0; b < 8; b++) {
            if (crc & 1) crc = (crc >> 1) ^ 0xA001;
            else         crc >>= 1;
        }
    }
    return crc; // émettre l'octet de poids faible PUIS le poids fort
}
```

```python
def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for x in data:
        crc ^= x
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc  # puis: bytes([crc & 0xFF, crc >> 8])
```

---

## 10. Récapitulatif des décisions de conception

| Décision | Recommandation |
|---|---|
| Option d'intégration | **A** (Modbus direct sur RS485) pour l'autonomie ; **B** (reconfig module → votre serveur TCP) pour éviter le câblage série |
| Premier travail technique | **Sniffing passif (§8.2 Méthode 1)** : trancher sens du polling, baud, FC, slave ID, scaling, adresses de lecture |
| Registres d'écriture | 2000=model{1,2,4}, 2001=switch{0,1}, 2002=function{1,2,4}, 2003=cooltemp(8..25), 2004=heattemp(15..40), 2006=autotemp(8..40) — **CONNUS** |
| Registres de lecture | **INCONNUS** — à cartographier au sniffing ; sémantique connue (ambiant, eau entrée/sortie, défaut, charge compresseur) |
| Scaling | côté app 1:1 ; **scaling final sur le fil À CONFIRMER** (probable ×10 températures, ÷10/÷5 capteurs) |
| Hypothèses ligne série | 9600 8N1, slave ID 1, FC 0x06 (écriture) / 0x03 (lecture) — **toutes À CONFIRMER** |

### Fichiers sources de référence (décompilation)

- `work\jadx_out\sources\com\heatpump\net\APIContext.java` — adresses 2000–2006 + clés
- `...\com\heatpump\bean\Constants.java` — commandes AT, énums modes/fonctions, hôtes, ports
- `...\com\heatpump\view\fragment\MainDeviceFragment.java` — logique d'écriture, plages, offsets
- `...\com\heatpump\entity\RtuRealTimes.java` + `RtuEnum.java` — champs télémétrie JSON
- `...\com\heatpump\net\service\ModelService.java` — endpoints REST
- `...\com\heatpump\rtuUtils\ATCommand.java`, `ModuleUtils.java`, `rtuUtils\net\*`, `rtuUtils\none\*` — provisionnement / pont transparent
