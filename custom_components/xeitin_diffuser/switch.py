"""Switch platform for XEITIN Diffuser."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    CHARACTERISTIC_UUID,
    PACKET_INIT,
    PACKET_POWER_ON,
    PACKET_POWER_OFF,
    PACKET_FAN_BOOST_ON,
    PACKET_FAN_BOOST_OFF,
    MODE_OPTIONS,
    MODE_PACKETS,
)

_LOGGER = logging.getLogger(__name__)

# No SCAN_INTERVAL - we don't poll the device (it beeps on every command)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up XEITIN Diffuser switches from a config entry."""
    address = hass.data[DOMAIN][entry.entry_id]["address"]
    if ":" not in address:
        address = ":".join(address[i:i+2].upper() for i in range(0, 12, 2))
    
    ble_device = XEITINBLEDevice(address)
    hass.data[DOMAIN][entry.entry_id]["ble_device"] = ble_device
    
    entities = [
        XEITINPowerSwitch(entry, ble_device),
        XEITINFanBoostSwitch(entry, ble_device),
    ]
    
    # Add individual mode switches (Mode I through Mode V)
    for idx, mode_name in enumerate(MODE_OPTIONS):
        entities.append(XEITINModeSwitch(entry, ble_device, idx, mode_name))
    
    async_add_entities(entities)


class XEITINBLEDevice:
    """Shared BLE device connection manager."""

    def __init__(self, address: str) -> None:
        self._address = address
        self._available = True  # Optimistic - assume available
        self._lock = asyncio.Lock()
        # State tracking (optimistic - no polling)
        self.power_on = False
        self.fan_boost = False
        self.modes_active = [False] * len(MODE_OPTIONS)  # Track each mode independently
        self.timer = 0  # Default timer value (0 = off)
        self.intensity = 5  # Default intensity (1-10)

    @property
    def address(self) -> str:
        return self._address

    @property
    def available(self) -> bool:
        return self._available

    async def send_command(self, packet: bytes, wait_response: bool = False) -> bool:
        """Send a command to the diffuser. Returns True on success."""
        async with self._lock:
            try:
                async with BleakClient(self._address, timeout=15.0) as client:
                    # Send init packet first
                    await client.write_gatt_char(CHARACTERISTIC_UUID, PACKET_INIT, response=False)
                    await asyncio.sleep(0.3)
                    # Send the actual command
                    await client.write_gatt_char(CHARACTERISTIC_UUID, packet, response=False)
                    await asyncio.sleep(0.2)
                self._available = True
                return True
            except BleakError as err:
                _LOGGER.warning("Failed to communicate with diffuser: %s", err)
                self._available = False
                return False


class XEITINBaseSwitchEntity(SwitchEntity):
    """Base class for XEITIN switches."""
    _attr_has_entity_name = True
    _attr_assumed_state = True  # Optimistic - we assume state after commands
    _attr_should_poll = False  # Don't poll - device beeps on every command

    def __init__(self, entry: ConfigEntry, ble_device: XEITINBLEDevice, name: str, key: str) -> None:
        self._ble_device = ble_device
        self._attr_unique_id = f"{ble_device.address.replace(chr(58), chr(95)).lower()}_{key}"
        self._attr_name = name
        self._entry = entry

    @property
    def available(self) -> bool:
        return self._ble_device.available

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._ble_device.address.replace(":", "").lower())},
            name="XEITIN Diffuser",
            manufacturer="XEITIN",
            model="Waterless Diffuser B501",
        )


class XEITINPowerSwitch(XEITINBaseSwitchEntity):
    """Power switch for XEITIN Diffuser."""
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:power"

    def __init__(self, entry: ConfigEntry, ble_device: XEITINBLEDevice) -> None:
        super().__init__(entry, ble_device, "Power", "power")

    @property
    def is_on(self) -> bool:
        return self._ble_device.power_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.info("Turning on XEITIN Diffuser")
        if await self._ble_device.send_command(PACKET_POWER_ON):
            self._ble_device.power_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("Turning off XEITIN Diffuser")
        if await self._ble_device.send_command(PACKET_POWER_OFF):
            self._ble_device.power_on = False
            self.async_write_ha_state()


class XEITINFanBoostSwitch(XEITINBaseSwitchEntity):
    """Fan boost switch for XEITIN Diffuser."""
    _attr_icon = "mdi:fan"

    def __init__(self, entry: ConfigEntry, ble_device: XEITINBLEDevice) -> None:
        super().__init__(entry, ble_device, "Fan Boost", "fan_boost")

    @property
    def is_on(self) -> bool:
        return self._ble_device.fan_boost

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.info("Enabling fan boost")
        if await self._ble_device.send_command(PACKET_FAN_BOOST_ON):
            self._ble_device.fan_boost = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("Disabling fan boost")
        if await self._ble_device.send_command(PACKET_FAN_BOOST_OFF):
            self._ble_device.fan_boost = False
            self.async_write_ha_state()


class XEITINModeSwitch(XEITINBaseSwitchEntity):
    """Individual mode/schedule switch for XEITIN Diffuser."""
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, entry: ConfigEntry, ble_device: XEITINBLEDevice, mode_idx: int, mode_name: str) -> None:
        # Create key like "mode_1", "mode_2", etc.
        key = f"mode_{mode_idx + 1}"
        super().__init__(entry, ble_device, mode_name, key)
        self._mode_idx = mode_idx
        self._mode_packet = MODE_PACKETS[mode_idx]

    @property
    def is_on(self) -> bool:
        return self._ble_device.modes_active[self._mode_idx]

    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.info("Enabling %s", self._attr_name)
        if await self._ble_device.send_command(self._mode_packet):
            self._ble_device.modes_active[self._mode_idx] = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Note: Device may not support disabling individual modes via BLE
        # This just tracks state locally - re-enabling may be needed on device
        _LOGGER.info("Disabling %s (local state only)", self._attr_name)
        self._ble_device.modes_active[self._mode_idx] = False
        self.async_write_ha_state()
