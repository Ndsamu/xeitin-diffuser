"""Select platform for XEITIN Diffuser mode selection."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    MODE_OPTIONS,
    MODE_PACKETS,
    TIMER_OPTIONS,
    TIMER_VALUES,
    TIMER_PACKETS,
)

_LOGGER = logging.getLogger(__name__)

# No SCAN_INTERVAL - we don't poll the device (it beeps on every command)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up XEITIN Diffuser select entities from a config entry."""
    ble_device = hass.data[DOMAIN][entry.entry_id]["ble_device"]
    
    async_add_entities([
        XEITINModeSelect(entry, ble_device),
        XEITINTimerSelect(entry, ble_device),
    ])


class XEITINModeSelect(SelectEntity):
    """Mode selection for XEITIN Diffuser."""

    _attr_has_entity_name = True
    _attr_name = "Mode"
    _attr_icon = "mdi:format-list-numbered"
    _attr_options = MODE_OPTIONS
    _attr_should_poll = False  # Don't poll - device beeps on every command
    _attr_assumed_state = True  # Optimistic mode

    def __init__(self, entry: ConfigEntry, ble_device) -> None:
        """Initialize the select entity."""
        self._ble_device = ble_device
        self._entry = entry
        self._attr_unique_id = f"{ble_device.address.replace(':', '').lower()}_mode"

    @property
    def available(self) -> bool:
        return self._ble_device.available

    @property
    def current_option(self) -> str | None:
        mode_idx = self._ble_device.mode
        if 0 <= mode_idx < len(MODE_OPTIONS):
            return MODE_OPTIONS[mode_idx]
        return MODE_OPTIONS[0]

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._ble_device.address.replace(":", "").lower())},
            name="XEITIN Diffuser",
            manufacturer="XEITIN",
            model="Waterless Diffuser B501",
        )

    async def async_select_option(self, option: str) -> None:
        """Change the selected mode."""
        try:
            idx = MODE_OPTIONS.index(option)
            _LOGGER.info("Setting mode to %s", option)
            await self._ble_device.send_command(MODE_PACKETS[idx], wait_response=False)
            self._ble_device.mode = idx
            self.async_write_ha_state()
        except ValueError:
            _LOGGER.error("Invalid mode option: %s", option)


class XEITINTimerSelect(SelectEntity):
    """Timer selection for XEITIN Diffuser."""

    _attr_has_entity_name = True
    _attr_name = "Timer"
    _attr_icon = "mdi:timer-outline"
    _attr_options = TIMER_OPTIONS
    _attr_should_poll = False  # Don't poll - device beeps on every command
    _attr_assumed_state = True  # Optimistic mode

    def __init__(self, entry: ConfigEntry, ble_device) -> None:
        """Initialize the select entity."""
        self._ble_device = ble_device
        self._entry = entry
        self._attr_unique_id = f"{ble_device.address.replace(':', '').lower()}_timer"

    @property
    def available(self) -> bool:
        return self._ble_device.available

    @property
    def current_option(self) -> str | None:
        timer_val = self._ble_device.timer
        try:
            idx = TIMER_VALUES.index(timer_val)
            return TIMER_OPTIONS[idx]
        except ValueError:
            return TIMER_OPTIONS[0]

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._ble_device.address.replace(":", "").lower())},
            name="XEITIN Diffuser",
            manufacturer="XEITIN",
            model="Waterless Diffuser B501",
        )

    async def async_select_option(self, option: str) -> None:
        """Change the timer setting."""
        try:
            idx = TIMER_OPTIONS.index(option)
            timer_val = TIMER_VALUES[idx]
            _LOGGER.info("Setting timer to %s (%d minutes)", option, timer_val)
            await self._ble_device.send_command(TIMER_PACKETS[timer_val], wait_response=False)
            self._ble_device.timer = timer_val
            self.async_write_ha_state()
        except (ValueError, KeyError) as err:
            _LOGGER.error("Invalid timer option: %s - %s", option, err)
