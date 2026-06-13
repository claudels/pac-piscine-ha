"""Decodeur du flux Modbus RTU de la PAC (bus RS485 via EW11 transparent)."""
from __future__ import annotations

from .const import MODES, FUNCS


def _crc_ok(f: bytes) -> bool:
    if len(f) < 4:
        return False
    c = 0xFFFF
    for x in f[:-2]:
        c ^= x
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return (c & 0xFF) == f[-2] and (c >> 8) == f[-1]


def _next_frame(b: bytes, i: int):
    n = len(b)
    if i + 4 > n:
        return None
    fc = b[i + 1]
    cands = []
    if fc in (1, 2, 3, 4):
        cands.append(8)
        if i + 3 <= n:
            cands.append(3 + b[i + 2] + 2)
    if fc == 16:
        cands.append(8)
        if i + 7 <= n:
            cands.append(7 + b[i + 6] + 2)
    if fc in (5, 6):
        cands.append(8)
    if fc & 0x80:
        cands.append(5)
    for L in sorted(set(cands)):
        if i + L <= n and _crc_ok(b[i:i + L]):
            return b[i:i + L]
    return None


def _regs(d: bytes):
    return [(d[2 * k] << 8) | d[2 * k + 1] for k in range(len(d) // 2)]


def decode_fault(code: int) -> str:
    if code == 0:
        return "OK"
    hi = code >> 8
    if 0x41 <= hi <= 0x5A:
        return "%s%02d" % (chr(hi), code & 0xFF)
    return "0x%04X" % code


class PacDecoder:
    """Accumule le flux TCP brut et en extrait l'etat de la PAC."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> dict:
        """Ajoute des octets recus, renvoie les champs decodes (peut etre vide)."""
        self._buf += data
        out: dict = {}
        i = 0
        consumed = 0
        n = len(self._buf)
        while i < n:
            f = _next_frame(self._buf, i)
            if not f:
                i += 1
                continue
            self._apply(bytes(f), out)
            i += len(f)
            consumed = i
        if consumed:
            del self._buf[:consumed]
        if len(self._buf) > 8192:
            del self._buf[:-2048]
        return out

    def _apply(self, f: bytes, out: dict) -> None:
        fc = f[1]
        if fc == 16 and len(f) > 8:
            addr = (f[2] << 8) | f[3]
            r = _regs(f[7:7 + f[6]])
            if addr == 0x07D0 and len(r) >= 7:
                out.update(self._ctrl(r))
            elif addr == 0x012C and len(r) >= 10:
                out.update(self._sensors(r))
            elif addr == 0x03E8 and len(r) >= 5:
                out["t_inlet"] = round(r[2] / 10.0, 1)
                out["fault"] = decode_fault(r[4])
                out["fault_active"] = r[4] != 0
            elif addr == 0x0190 and len(r) >= 5:
                out["fault_history"] = [decode_fault(c) for c in r[1:5] if c]
        elif fc == 3 and len(f) > 5 and f[2] == 14:
            r = _regs(f[3:3 + f[2]])
            if len(r) >= 7:
                out.update(self._ctrl(r))

    @staticmethod
    def _ctrl(r):
        return {
            "power": bool(r[1]),
            "mode": MODES.get(r[0], "?"),
            "function": FUNCS.get(r[2], "?"),
            "set_cool": r[3],
            "set_heat": r[4],
            "set_auto": r[6],
        }

    @staticmethod
    def _sensors(r):
        return {
            "comp_freq": r[0],
            "eev": r[1],
            "t_ambient": r[2],
            "t_outlet": r[3],
            "t_discharge": r[4],
            "t_suction": r[5],
            "t_coil_t3": r[6],
            "t_4way": r[7],
            "pump": bool(r[8]),
            "compressor": r[0] > 0,
        }
