"""Die Ladegrenze als einstellbarer Wert.

Hier liegt der groesste Unterschied zu ioBroker: Home Assistant erzwingt
Minimum, Maximum und Schrittweite selbst in der Oberflaeche. Die gemessene
Untergrenze steht damit nicht nur im Code - der Schieberegler geht gar nicht
tiefer.
"""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AmbiconnectEntry
from .entity import AmbiboxEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: AmbiconnectEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([AmbiboxChargeLimit(entry.runtime_data)])


class AmbiboxChargeLimit(AmbiboxEntity, NumberEntity):
    """Ladegrenze in Watt, bezogen auf die DC-Seite."""

    _attr_name = "Ladegrenze"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_step = 100
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:speedometer"

    def __init__(self, hub) -> None:
        super().__init__(hub, "limitChargePower")

    @property
    def native_min_value(self) -> float:
        return float(self._hub.min_power)

    @property
    def native_max_value(self) -> float:
        return float(self._hub.max_power)

    @property
    def native_value(self) -> float | None:
        # Die Box meldet die gesetzte Grenze nicht zurueck. Der zuletzt
        # gesendete Wert ist das Beste, was wir wissen - die tatsaechliche
        # Wirkung steht im Sensor "Ladeleistung DC".
        return self._hub._applied

    @property
    def available(self) -> bool:
        return self._hub.available and self._hub.control_enabled

    async def async_set_native_value(self, value: float) -> None:
        await self._hub.async_set_limit(value)
        self.async_write_ha_state()
