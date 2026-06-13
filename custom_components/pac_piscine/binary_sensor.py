"""Capteurs binaires PAC Piscine."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BINARY_SENSORS, DOMAIN
from .coordinator import PacCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: PacCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(PacBinarySensor(coordinator, entry, *b) for b in BINARY_SENSORS)


class PacBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Un capteur on/off de la PAC."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, name, dclass, icon):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_class = dclass
        if icon:
            self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="PAC Piscine",
            manufacturer="AXEN (OEM) - POWER S INV",
            model="DC Inverter - RS485 Modbus (EW11)",
        )

    @property
    def is_on(self):
        data = self.coordinator.data or {}
        return bool(data.get(self._key))
