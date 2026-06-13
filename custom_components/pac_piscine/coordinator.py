"""Coordinator : maintient une connexion TCP a l'EW11 et pousse l'etat decode."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .decoder import PacDecoder

_LOGGER = logging.getLogger(__name__)


class PacCoordinator(DataUpdateCoordinator):
    """Lecteur passif du bus PAC via EW11 (mode push, pas de polling)."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self._host = host
        self._port = port
        self._decoder = PacDecoder()
        self._state: dict = {}
        self._task: asyncio.Task | None = None

    async def async_start(self) -> None:
        self._task = self.hass.async_create_background_task(
            self._listen(), name=f"{DOMAIN}_listener"
        )

    async def async_stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    async def _listen(self) -> None:
        while True:
            writer = None
            try:
                _LOGGER.debug("Connexion a l'EW11 %s:%s", self._host, self._port)
                reader, writer = await asyncio.open_connection(self._host, self._port)
                while True:
                    data = await reader.read(4096)
                    if not data:
                        raise ConnectionError("EW11 a ferme la connexion")
                    updates = self._decoder.feed(data)
                    if updates:
                        self._state.update(updates)
                        if "t_inlet" in self._state and "t_outlet" in self._state:
                            self._state["water_delta"] = round(
                                self._state["t_outlet"] - self._state["t_inlet"], 1
                            )
                        self.async_set_updated_data(dict(self._state))
            except asyncio.CancelledError:
                if writer:
                    writer.close()
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("EW11 deconnecte (%s), nouvelle tentative dans 5s", err)
                if writer:
                    try:
                        writer.close()
                    except Exception:  # noqa: BLE001
                        pass
                await asyncio.sleep(5)
