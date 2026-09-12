"""Wecken und Stoppen als Knoepfe."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AmbiconnectEntry
from .entity import AmbiboxEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: AmbiconnectEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub = entry.runtime_data
    async_add_entities([AmbiboxWakeButton(hub), AmbiboxStopButton(hub)])


class _ControlButton(AmbiboxEntity, ButtonEntity):
    @property
    def available(self) -> bool:
        return self._hub.available and self._hub.control_enabled


class AmbiboxWakeButton(_ControlButton):
    """Startet eine Ladesitzung - der einzige Befehl, der das kann."""

    _attr_name = "Ladung starten"
    _attr_icon = "mdi:play"

    def __init__(self, hub) -> None:
        super().__init__(hub, "wakeUp")

    async def async_press(self) -> None:
        await self._hub.async_wake()


class AmbiboxStopButton(_ControlButton):
    """Beendet die Ladung - im Startfenster verweigert, weil das Neustecken erzwingt."""

    _attr_name = "Ladung beenden"
    _attr_icon = "mdi:stop"

    def __init__(self, hub) -> None:
        super().__init__(hub, "stopCharge")

    async def async_press(self) -> None:
        await self._hub.async_stop_charge()
