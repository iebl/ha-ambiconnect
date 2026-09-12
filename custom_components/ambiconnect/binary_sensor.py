"""Ja/Nein-Zustaende der Box."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AmbiconnectEntry
from .entity import AmbiboxEntity


@dataclass(frozen=True, kw_only=True)
class AmbiboxBinaryDescription(BinarySensorEntityDescription):
    topic: str


SENSORS: tuple[AmbiboxBinaryDescription, ...] = (
    AmbiboxBinaryDescription(
        key="evConnected", topic="evConnected", name="Fahrzeug verbunden",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    AmbiboxBinaryDescription(
        # Nur durch koerperliches Aus- und Einstecken zu loesen - kein Befehl
        # hilft. Deshalb als Problem gemeldet und nicht bloss als Zustand.
        key="replugRequired", topic="replugRequired", name="Neustecken noetig",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    AmbiboxBinaryDescription(
        # Die Box sperrt das Wecken nach einem Sitzungsstart fuer eine Weile.
        # Die Dauer schwankt, deshalb wird das Flag gelesen statt gerechnet.
        key="wakeUpBlocked", topic="wakeUpBlocked", name="Wecken gesperrt",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AmbiboxBinaryDescription(
        key="sleep", topic="sleep", name="Schlafend",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: AmbiconnectEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        AmbiboxBinarySensor(entry.runtime_data, d) for d in SENSORS
    )


class AmbiboxBinarySensor(AmbiboxEntity, BinarySensorEntity):
    entity_description: AmbiboxBinaryDescription

    def __init__(self, hub, description: AmbiboxBinaryDescription) -> None:
        super().__init__(hub, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self._hub.values.get(self.entity_description.topic)
