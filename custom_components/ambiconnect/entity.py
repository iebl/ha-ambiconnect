"""Gemeinsame Basis aller AMBIConnect-Entitaeten."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_UPDATE
from .hub import AmbiboxHub


class AmbiboxEntity(Entity):
    """Haengt alle Entitaeten an ein Geraet und an dieselbe Aktualisierung."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: AmbiboxHub, key: str) -> None:
        self._hub = hub
        self._key = key
        self._attr_unique_id = f"{hub.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        serial = self._hub.values.get("serialNumber")
        return DeviceInfo(
            identifiers={(DOMAIN, serial or self._hub.entry_id)},
            manufacturer="Ambibox",
            model="ambiCHARGE Home",
            name="Ambibox",
            serial_number=serial,
            sw_version=self._hub.values.get("version"),
            configuration_url=f"http://{self._hub.host}",
        )

    @property
    def available(self) -> bool:
        return self._hub.available

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_UPDATE}_{self._hub.entry_id}",
                self.async_write_ha_state,
            )
        )
