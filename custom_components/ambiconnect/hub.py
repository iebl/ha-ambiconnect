"""MQTT-Anbindung und Sicherheitsschicht der Ambibox ambiCHARGE Home.

Der Grund, warum diese Integration kein duenner MQTT-Durchreicher ist: bei
dieser Box ist ein beschreibbarer Zahlenwert kein Bedienelement, sondern eine
Falle. Alle Regeln hier sind an der realen Box gemessen, nicht geraten.

  - Eine Ladegrenze unter dem Arbeitspunkt der Leistungsendstufe loest diese aus
    und beendet die Sitzung. Die Box begrenzt nicht selbst: sie uebernimmt den
    Wert wortwoertlich und stolpert darueber.
  - Eine Null ist keine Pause. Ohne stopCharge haelt die Sitzung rund 66 s und
    stirbt dann endgueltig.
  - stopCharge waehrend des Startvorgangs wirft die Box in ERROR und verlangt
    koerperliches Neustecken. Kein Befehl holt sie da heraus.
  - Ein wakeUp in ein Fahrzeug hinein, das gerade nicht laden will, laeuft in den
    SLAC-Timeout und endet ebenso.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import paho.mqtt.client as mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    BOOL_TOPICS,
    INACTIVE_STATES,
    INVERTED_TOPICS,
    NUMERIC_TOPICS,
    SIGNAL_UPDATE,
    STARTUP_WINDOW_S,
    STATE_CHARGE_LOOP,
    WAKE_GRACE_S,
    WAKE_QUIET_S,
)

_LOGGER = logging.getLogger(__name__)


class AmbiboxHub:
    """Haelt die Verbindung zur Box und entscheidet, was gesendet werden darf."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        device_topic: str,
        control_enabled: bool,
        min_power: int,
        ramp_factor: float,
        entry_id: str,
    ) -> None:
        self.hass = hass
        self.host = host
        self.port = port
        self.device_topic = device_topic.rstrip("/")
        self.control_enabled = control_enabled
        self.min_power = min_power
        self.ramp_factor = ramp_factor
        self.entry_id = entry_id

        self.values: dict[str, Any] = {}
        self.available = False

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username:
            self._client.username_pw_set(username, password or None)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # Sollwert und zuletzt gesendeter Wert der Ladegrenze
        self._target: int | None = None
        self._applied: int | None = None

        self._woke_at = None
        self._wake_quiet_until = None
        self._stop_requested = False
        self._vehicle_stopped = False
        self._was_active = False
        self._was_connected = False

    # ------------------------------------------------------------------ Leben

    async def async_start(self) -> None:
        """Verbindet im Hintergrund; paho bringt seinen eigenen Thread mit."""
        await self.hass.async_add_executor_job(self._connect)

    def _connect(self) -> None:
        self._client.connect(self.host, self.port, keepalive=60)
        self._client.loop_start()

    async def async_stop(self) -> None:
        await self.hass.async_add_executor_job(self._disconnect)

    def _disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    # -------------------------------------------------------------- Callbacks

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code != 0:
            _LOGGER.error("Broker lehnt die Verbindung ab: %s", reason_code)
            return
        _LOGGER.info("Broker verbunden: %s:%s", self.host, self.port)
        client.subscribe(f"{self.device_topic}/#")
        self.available = True
        self._notify()

    def _on_disconnect(self, client, userdata, *args):
        self.available = False
        self._notify()

    def _on_message(self, client, userdata, msg):
        name = msg.topic[len(self.device_topic) + 1 :]
        raw = msg.payload.decode(errors="replace")
        value = self._parse(name, raw)
        self.values[name] = value

        if name in ("sessionState", "evConnected"):
            self._observe()

        self._notify()

    def _parse(self, name: str, raw: str) -> Any:
        # Leere Nutzlast: die Box loescht einen retained Wert. Das heisst
        # "nicht vorhanden", nicht "leerer Text".
        if raw == "":
            return None
        if name in BOOL_TOPICS:
            return raw in ("true", "1")
        if name in NUMERIC_TOPICS:
            try:
                number = float(raw)
            except ValueError:
                return None
            return -number if name in INVERTED_TOPICS else number
        return raw

    @callback
    def _notify(self) -> None:
        self.hass.loop.call_soon_threadsafe(
            async_dispatcher_send, self.hass, f"{SIGNAL_UPDATE}_{self.entry_id}"
        )

    # ----------------------------------------------------------- Beobachtung

    def _observe(self) -> None:
        """Merkt sich zwei Momente, die die Box nicht als Ereignis meldet.

        Eine Sitzung, die endet, ohne dass wir darum gebeten haben, ist die
        Entscheidung des Fahrzeugs - der Normalfall beim tarifgesteuerten Laden.
        Sofort wieder zu wecken kostet einen Gang zum Auto.
        """
        active = self.session_active
        if self._was_active and not active:
            if self._stop_requested:
                self._stop_requested = False
            else:
                self._vehicle_stopped = True
                _LOGGER.info(
                    "Sitzung endete ohne unser Zutun - das Fahrzeug hat entschieden, "
                    "es wird nicht nachgeweckt"
                )
        self._was_active = active

        connected = bool(self.values.get("evConnected"))
        if connected and not self._was_connected:
            self._vehicle_stopped = False
        self._was_connected = connected

    # -------------------------------------------------------------- Zustaende

    @property
    def session_active(self) -> bool:
        state = self.values.get("sessionState")
        return bool(state) and state not in INACTIVE_STATES

    @property
    def charging(self) -> bool:
        return self.values.get("sessionState") == STATE_CHARGE_LOOP

    @property
    def starting_up(self) -> bool:
        if self._woke_at is None or self.charging:
            return False
        return (dt_util.utcnow() - self._woke_at).total_seconds() < STARTUP_WINDOW_S

    @property
    def max_power(self) -> int:
        return int(self.values.get("chargePowerMax") or 10200)

    # ---------------------------------------------------------------- Befehle

    def _publish(self, topic: str, payload: str, retain: bool = False) -> None:
        # Befehle bewusst ohne retain: ein liegengebliebenes wakeUp=true wuerde
        # die Box beim naechsten Verbindungsaufbau erneut wecken.
        self._client.publish(f"{self.device_topic}/{topic}", payload, retain=retain)

    async def async_set_limit(self, watts: float) -> None:
        """Nimmt einen Grenzwunsch entgegen und klemmt ihn in den Arbeitsbereich."""
        if not self.control_enabled:
            _LOGGER.warning("Steuerung ist gesperrt - Ladegrenze nicht gesetzt")
            return

        if watts <= 0:
            _LOGGER.warning(
                "Null ist bei dieser Box keine Pause - nutze den Stopp-Knopf"
            )
            return

        target = int(round(watts))
        if target < self.min_power:
            _LOGGER.warning(
                "Ladegrenze %s W liegt unter dem Minimum, auf %s W angehoben",
                target, self.min_power,
            )
            target = self.min_power
        target = min(target, self.max_power)

        self._target = target
        await self.hass.async_add_executor_job(self._step)

    def _step(self) -> None:
        """Ein Schritt Richtung Ziel: abwaerts hoechstens ein Rampenschritt."""
        if self._target is None:
            return
        if self._applied is None or self._target >= self._applied:
            self._send_limit(self._target)
            return
        nxt = max(self._target, int(round(self._applied * self.ramp_factor)))
        self._send_limit(nxt)

    def _send_limit(self, watts: int) -> None:
        if watts == self._applied:
            return
        self._publish("limitChargePower", str(watts), retain=True)
        self._applied = watts

    async def async_ramp_tick(self) -> None:
        """Wird im Takt aufgerufen; setzt einen begonnenen Abstieg fort."""
        if self._target is not None and self._applied != self._target and self.charging:
            await self.hass.async_add_executor_job(self._step)

    async def async_wake(self) -> bool:
        """Weckt die Box - wenn nichts dagegen spricht."""
        if not self.control_enabled:
            _LOGGER.warning("Steuerung ist gesperrt - nicht geweckt")
            return False

        if self.values.get("replugRequired"):
            _LOGGER.warning(
                "Die Box verlangt koerperliches Neustecken - kein Befehl hilft"
            )
            return False

        if self.values.get("wakeUpBlocked"):
            # Die Dauer ist keine Konstante - 5:00 und 2:49 am selben Tag
            # gemessen -, also wird das Flag gelesen statt eine Wartezeit
            # angenommen.
            _LOGGER.debug("Box meldet wakeUpBlocked - nicht geweckt")
            return False

        if self._vehicle_stopped:
            _LOGGER.debug("Das Fahrzeug beendete die letzte Sitzung selbst")
            return False

        if self.session_active:
            _LOGGER.debug("Eine Sitzung laeuft oder baut sich auf")
            return False

        now = dt_util.utcnow()
        if self._woke_at and (now - self._woke_at).total_seconds() < WAKE_GRACE_S:
            _LOGGER.debug("Ein Weckruf laeuft noch")
            return False
        if self._wake_quiet_until and now < self._wake_quiet_until:
            _LOGGER.debug("Ruhephase nach unbeantwortetem Weckruf")
            return False

        # Grenze zuerst: eine ohne Limit gestartete Sitzung faehrt auf das
        # Maximum der Box hoch.
        if self._applied is None:
            await self.hass.async_add_executor_job(self._send_limit, self.min_power)

        await self.hass.async_add_executor_job(self._publish, "wakeUp", "true")
        self._woke_at = now
        self._wake_quiet_until = None
        return True

    def note_wake_unanswered(self) -> None:
        """Nach WAKE_GRACE_S ohne Sitzung: Ruhe geben statt nachzusetzen."""
        if self._woke_at is None or self.session_active:
            return
        elapsed = (dt_util.utcnow() - self._woke_at).total_seconds()
        if elapsed < WAKE_GRACE_S or self._wake_quiet_until:
            return
        self._wake_quiet_until = dt_util.utcnow() + timedelta(seconds=WAKE_QUIET_S)
        _LOGGER.warning(
            "Weckruf blieb unbeantwortet - das Fahrzeug will nicht laden, "
            "naechster Versuch fruehestens in %s s", WAKE_QUIET_S,
        )

    async def async_stop_charge(self) -> bool:
        """Beendet die Ladung - aber nur, wenn das gefahrlos ist."""
        if not self.control_enabled:
            _LOGGER.warning("Steuerung ist gesperrt - nicht gestoppt")
            return False

        self._vehicle_stopped = False
        self._stop_requested = True

        if self.charging:
            await self.hass.async_add_executor_job(self._publish, "stopCharge", "true")
            self._target = None
            self._applied = None
            return True

        if self.starting_up:
            _LOGGER.warning(
                "Die Box startet noch - ein Stopp jetzt wuerde Neustecken erzwingen"
            )
            return False

        _LOGGER.debug("Keine Ladung aktiv, Stopp verworfen")
        return False
