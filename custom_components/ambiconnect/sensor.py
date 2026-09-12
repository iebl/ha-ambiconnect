"""Messwerte der Box als Sensoren.

Die Typisierung ist hier der eigentliche Gewinn gegenueber einem generischen
MQTT-Durchgriff: aus `device_class` und `state_class` leitet Home Assistant
Symbol, Diagramm und Langzeitstatistik ab - und die Energiezaehler landen ohne
weiteres Zutun im Energie-Dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AmbiconnectEntry
from .entity import AmbiboxEntity


@dataclass(frozen=True, kw_only=True)
class AmbiboxSensorDescription(SensorEntityDescription):
    """Beschreibung samt Topic."""

    topic: str


def _power(key: str, name: str) -> AmbiboxSensorDescription:
    return AmbiboxSensorDescription(
        key=key, topic=key, name=name,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    )


def _energy(key: str, name: str) -> AmbiboxSensorDescription:
    return AmbiboxSensorDescription(
        key=key, topic=key, name=name,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    )


def _current(key: str, name: str) -> AmbiboxSensorDescription:
    return AmbiboxSensorDescription(
        key=key, topic=key, name=name,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_registry_enabled_default=False,
    )


def _voltage(key: str, name: str) -> AmbiboxSensorDescription:
    return AmbiboxSensorDescription(
        key=key, topic=key, name=name,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_registry_enabled_default=False,
    )


SENSORS: tuple[AmbiboxSensorDescription, ...] = (
    _power("powerAc", "Ladeleistung AC"),
    # Die Steuergroesse: limitChargePower wirkt auf die DC-Seite, powerAc traegt
    # zusaetzlich den Wandlungsverlust. 700 W Grenze entsprachen 682 W DC und
    # 875 W AC.
    _power("powerDc", "Ladeleistung DC"),
    _energy("energyAcImport", "Energie bezogen"),
    _energy("energyAcExport", "Energie abgegeben"),
    _energy("energyAcImportSession", "Energie diese Sitzung"),
    _current("currentAc", "Strom AC"),
    _current("currentAc1", "Strom L1"),
    _current("currentAc2", "Strom L2"),
    _current("currentAc3", "Strom L3"),
    _current("currentDc", "Strom DC"),
    _voltage("voltageAc", "Spannung AC"),
    _voltage("voltageAc1", "Spannung L1"),
    _voltage("voltageAc2", "Spannung L2"),
    _voltage("voltageAc3", "Spannung L3"),
    _voltage("voltageDc", "Spannung DC"),
    AmbiboxSensorDescription(
        key="soc", topic="soc", name="Ladestand Fahrzeug",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    AmbiboxSensorDescription(
        key="inverterTemperature", topic="inverterTemperature", name="Temperatur",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AmbiboxSensorDescription(
        key="frequency", topic="frequency", name="Netzfrequenz",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    AmbiboxSensorDescription(
        key="sessionState", topic="sessionState", name="Sitzungszustand",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "STOPPED", "SESSION_SETUP", "CHARGE_PARAMETER_DISCOVERY", "CABLE_CHECK",
            "PRE_CHARGE", "CHARGE_LOOP", "POST_CHARGE", "ERROR",
        ],
    ),
    AmbiboxSensorDescription(
        key="chargeProtocol", topic="chargeProtocol", name="Ladeprotokoll",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AmbiboxSensorDescription(
        # LIMITABLE heisst: die Box nimmt Grenzen an, aber keine Sollwerte. Das
        # haengt am Lademodus des Fahrzeugs, nicht an der Box.
        key="controlMode", topic="controlMode", name="Steuermodus",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AmbiboxSensorDescription(
        # Die Box meldet hier nur OTHER_ALARM. Der genaue Code steht
        # ausschliesslich in den Modbus-Registern 4044 und 4096.
        key="inverterError", topic="inverterError", name="Wechselrichterfehler",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AmbiboxSensorDescription(
        key="chargePowerMax", topic="chargePowerMax", name="Hoechste Ladeleistung",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: AmbiconnectEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        AmbiboxSensor(entry.runtime_data, description) for description in SENSORS
    )


class AmbiboxSensor(AmbiboxEntity, SensorEntity):
    """Ein Messwert der Box."""

    entity_description: AmbiboxSensorDescription

    def __init__(self, hub, description: AmbiboxSensorDescription) -> None:
        super().__init__(hub, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self._hub.values.get(self.entity_description.topic)
