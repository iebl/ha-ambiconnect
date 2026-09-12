"""Konstanten und Topic-Landkarte der Ambibox ambiCHARGE Home.

Gemessen an Firmware 0.4.8 (Manny). Die Vorzeichenkonvention der Box ist
ungewoehnlich: Leistung ist beim *Laden* negativ. Home Assistant erwartet bei
`device_class: power` das Gegenteil, deshalb dreht der Hub das Vorzeichen fuer
die Anzeige um - einmal, zentral, damit es nicht an zwanzig Stellen passiert.
"""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ambiconnect"

CONF_DEVICE_TOPIC: Final = "device_topic"
CONF_CONTROL_ENABLED: Final = "control_enabled"
CONF_MIN_POWER: Final = "min_power_w"
CONF_RAMP_FACTOR: Final = "ramp_factor"
CONF_RAMP_INTERVAL: Final = "ramp_interval_s"

DEFAULT_PORT: Final = 1883
DEFAULT_DEVICE_TOPIC: Final = "device/evCharger/0"

# Untergrenze der Leistungsendstufe. Gemessen am 12.09.2026 mit abgeschaltetem
# ChargeControl der Box: 510 W laufen stabil, 459 W loesen sie aus und beenden
# die Ladesitzung. 600 W haelt Abstand und ist zugleich der Wert, den die Box
# selbst als Minimum meldet (ESS-Eingangsregister 6002) - ohne ihn durchzusetzen.
DEFAULT_MIN_POWER: Final = 600

# Fuenf Abstiege von 10200 auf 700 W haben alle gehalten, bis einschliesslich
# -40 % alle 5 s. Hier steht die Haelfte davon.
DEFAULT_RAMP_FACTOR: Final = 0.8
DEFAULT_RAMP_INTERVAL: Final = 5

# Ein stopCharge waehrend des Startvorgangs wirft die Box in ERROR und verlangt
# koerperliches Neustecken. Die Box zeigt dieses Fenster nicht an - sessionState
# bleibt durchgehend STOPPED -, also wird ab dem eigenen wakeUp gezaehlt.
STARTUP_WINDOW_S: Final = 45
STOP_DEFERRAL_S: Final = 120

# Ein wakeUp in ein Fahrzeug hinein, das nicht laden will, laeuft in den
# SLAC-Timeout (50 s), wirft die Box in ERROR und endet in replugRequired.
WAKE_GRACE_S: Final = 75
WAKE_QUIET_S: Final = 300

SIGNAL_UPDATE: Final = f"{DOMAIN}_update"

# Sessionzustaende, wie die Box sie auf `sessionState` veroeffentlicht
STATE_STOPPED: Final = "STOPPED"
STATE_ERROR: Final = "ERROR"
STATE_POST_CHARGE: Final = "POST_CHARGE"
STATE_CHARGE_LOOP: Final = "CHARGE_LOOP"

INACTIVE_STATES: Final = frozenset({"", STATE_STOPPED, STATE_ERROR, STATE_POST_CHARGE})

# Topics, die als Wahrheitswert ankommen
BOOL_TOPICS: Final = frozenset(
    {"connected", "evConnected", "replugRequired", "wakeUpBlocked", "sleep"}
)

# Topics, die als Zahl ankommen
NUMERIC_TOPICS: Final = frozenset(
    {
        "powerAc", "powerDc", "currentAc", "currentAc1", "currentAc2", "currentAc3",
        "currentDc", "voltageAc", "voltageAc1", "voltageAc2", "voltageAc3", "voltageDc",
        "frequency", "inverterTemperature", "energyAc", "energyAcImport",
        "energyAcExport", "energyAcImportSession", "energyAcExportSession",
        "soc", "targetEnergyRequest", "chargePowerMax", "dischargePowerMax",
        "limitChargePower",
    }
)

# Leistungstopics, deren Vorzeichen fuer die Anzeige gedreht wird
INVERTED_TOPICS: Final = frozenset({"powerAc", "powerDc", "currentDc"})
