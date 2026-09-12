"""Einrichtung ueber die Oberflaeche."""

from __future__ import annotations

import contextlib
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CONTROL_ENABLED,
    CONF_DEVICE_TOPIC,
    CONF_MIN_POWER,
    CONF_RAMP_FACTOR,
    CONF_RAMP_INTERVAL,
    DEFAULT_DEVICE_TOPIC,
    DEFAULT_MIN_POWER,
    DEFAULT_PORT,
    DEFAULT_RAMP_FACTOR,
    DEFAULT_RAMP_INTERVAL,
    DOMAIN,
)

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_USERNAME, default=""): cv.string,
        vol.Optional(CONF_PASSWORD, default=""): cv.string,
        vol.Required(CONF_DEVICE_TOPIC, default=DEFAULT_DEVICE_TOPIC): cv.string,
    }
)


async def _probe(hass, data: dict[str, Any]) -> str | None:
    """Prueft die Verbindung, bevor der Eintrag entsteht."""
    import paho.mqtt.client as mqtt

    def _try() -> str | None:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if data.get(CONF_USERNAME):
            client.username_pw_set(data[CONF_USERNAME], data.get(CONF_PASSWORD) or None)
        try:
            client.connect(data[CONF_HOST], data[CONF_PORT], keepalive=10)
        except OSError:
            return "cannot_connect"
        except Exception:  # noqa: BLE001 - der Broker kann alles Moegliche werfen
            return "invalid_auth"
        finally:
            with contextlib.suppress(Exception):
                client.disconnect()
        return None

    return await hass.async_add_executor_job(_try)


class AmbiconnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fragt die Verbindungsdaten ab."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if error := await _probe(self.hass, user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(title="Ambibox", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return AmbiconnectOptionsFlow()


class AmbiconnectOptionsFlow(OptionsFlow):
    """Steuerung freigeben und die Sicherheitswerte anpassen."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONTROL_ENABLED,
                    default=current.get(CONF_CONTROL_ENABLED, False),
                ): cv.boolean,
                vol.Required(
                    CONF_MIN_POWER, default=current.get(CONF_MIN_POWER, DEFAULT_MIN_POWER)
                ): vol.All(vol.Coerce(int), vol.Range(min=100, max=5000)),
                vol.Required(
                    CONF_RAMP_FACTOR,
                    default=current.get(CONF_RAMP_FACTOR, DEFAULT_RAMP_FACTOR),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=1.0)),
                vol.Required(
                    CONF_RAMP_INTERVAL,
                    default=current.get(CONF_RAMP_INTERVAL, DEFAULT_RAMP_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
