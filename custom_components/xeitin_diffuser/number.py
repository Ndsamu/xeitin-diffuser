"""Number platform for XEITIN Diffuser intensity control."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, INTENSITY_PACKETS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up XEITIN Diffuser number entities from a config entry."""
    ble_device = hass.data[DOMAIN][entry.entry_id]["ble_device"]
    
    async_add_entities([XEITINIntensityNumber(entry, ble_device)])


class XEITINIntensityNumber(NumberEntity):
    """Intensity control for XEITIN Diffuser."""

    _attr_has_entity_name = True
    _attr_name = "Intensity"
    _attr_icon = "mdi:gauge"
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, entry: ConfigEntry, ble_device) -> None:
        """Initialize the number entity."""
        self._ble_device = ble_device
        self._entry = entry
        self._attr_unique_id = f"{ble_device.address.replace(':', '').lower()}_intensity"

    @property
    def available(self) -> bool:
        return self._ble_device.available

    @property
    def native_value(self) -> float:
        return float(self._ble_device.intensity)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._ble_device.address.replace(":", "").lower())},
            name="XEITIN Diffuser",
            manufacturer="XEITIN",
            model="Waterless Diffuser B501",
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the intensity level."""
        level = int(value)
        if level < 1:
            level = 1
        elif level > 10:
            level = 10
            
        _LOGGER.info("Setting intensity to %d", level)
        
        if level in INTENSITY_PACKETS:
            await self._ble_device.send_command(INTENSITY_PACKETS[level], wait_response=False)
            self._ble_device.intensity = level
            self.async_write_ha_state()
        else:
            _LOGGER.error("Invalid intensity level: %d", level)
