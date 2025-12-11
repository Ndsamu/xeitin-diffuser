"""Config flow for XEITIN Diffuser integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_DEVICE_ADDRESS

_LOGGER = logging.getLogger(__name__)


class XEITINDiffuserConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for XEITIN Diffuser."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_DEVICE_ADDRESS]
            await self.async_set_unique_id(address.replace(":", "").lower())
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=f"XEITIN Diffuser ({address[-8:]})",
                data={CONF_DEVICE_ADDRESS: address},
            )

        # Try to discover Scent devices via Bluetooth
        self._discovered_devices = {}
        for discovery_info in async_discovered_service_info(self.hass):
            if discovery_info.name and discovery_info.name.startswith("Scent-"):
                self._discovered_devices[discovery_info.address] = discovery_info.name

        if self._discovered_devices:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_DEVICE_ADDRESS): vol.In(
                            {addr: f"{name} ({addr})" for addr, name in self._discovered_devices.items()}
                        )
                    }
                ),
                errors=errors,
            )

        # Manual entry if no devices found
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ADDRESS): str,
                }
            ),
            description_placeholders={
                "device_address": "E4:66:E5:69:91:81"
            },
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address.replace(":", "").lower())
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {
            "name": discovery_info.name or "XEITIN Diffuser"
        }

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm bluetooth discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.context["title_placeholders"]["name"],
                data={CONF_DEVICE_ADDRESS: self.unique_id},
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
        )
