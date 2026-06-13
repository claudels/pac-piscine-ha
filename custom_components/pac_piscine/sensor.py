"""Capteurs PAC Piscine."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSORS
from .coordinator import PacCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: PacCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(PacSensor(coordinator, entry, *s) for s in SENSORS)


class PacSensor(CoordinatorEntity, SensorEntity):
    """Un capteur lu depuis le bus de la PAC."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, name, unit, dclass, sclass, icon):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dclass
        self._attr_state_class = sclass
        if icon:
            self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="PAC Piscine",
            manufacturer="AXEN (OEM) - POWER S INV",
            model="DC Inverter - RS485 Modbus (EW11)",
        )

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return data.get(self._key)

    @property
    def extra_state_attributes(self):
        if self._key == "fault":
            data = self.coordinator.data or {}
            hist = data.get("fault_history")
            if hist:
                return {"historique": ", ".join(hist)}
        return None
