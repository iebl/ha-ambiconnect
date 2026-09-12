"""AMBIConnect - Ambibox ambiCHARGE Home fuer Home Assistant."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_CONTROL_ENABLED,
    CONF_DEVICE_TOPIC,
    CONF_MIN_POWER,
    CONF_RAMP_FACTOR,
    CONF_RAMP_INTERVAL,
    DEFAULT_DEVICE_TOPIC,
    DEFAULT_MIN_POWER,
    DEFAULT_RAMP_FACTOR,
    DEFAULT_RAMP_INTERVAL,
)
from .hub import AmbiboxHub

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
]

type AmbiconnectEntry = ConfigEntry[AmbiboxHub]


async def async_setup_entry(hass: HomeAssistant, entry: AmbiconnectEntry) -> bool:
    """Verbindung aufbauen und Entitaeten anlegen."""
    options = {**entry.data, **entry.options}

    hub = AmbiboxHub(
        hass,
        host=options[CONF_HOST],
        port=options.get(CONF_PORT, 1883),
        username=options.get(CONF_USERNAME),
        password=options.get(CONF_PASSWORD),
        device_topic=options.get(CONF_DEVICE_TOPIC, DEFAULT_DEVICE_TOPIC),
        control_enabled=options.get(CONF_CONTROL_ENABLED, False),
        min_power=options.get(CONF_MIN_POWER, DEFAULT_MIN_POWER),
        ramp_factor=options.get(CONF_RAMP_FACTOR, DEFAULT_RAMP_FACTOR),
        entry_id=entry.entry_id,
    )

    await hub.async_start()
    entry.runtime_data = hub

    interval = timedelta(seconds=options.get(CONF_RAMP_INTERVAL, DEFAULT_RAMP_INTERVAL))

    async def _tick(_now) -> None:
        # Die Box meldet weder "Sitzung beendet" noch "Weckruf unbeantwortet"
        # als Ereignis - beides muss im Takt nachgesehen werden.
        await hub.async_ramp_tick()
        hub.note_wake_unanswered()

    entry.async_on_unload(async_track_time_interval(hass, _tick, interval))
    entry.async_on_unload(entry.add_update_listener(_reload_on_change))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _reload_on_change(hass: HomeAssistant, entry: AmbiconnectEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AmbiconnectEntry) -> bool:
    """Verbindung trennen."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
