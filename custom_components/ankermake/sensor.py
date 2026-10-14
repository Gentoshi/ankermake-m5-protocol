import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DATA_COORDINATOR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AnkerMake sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    
    entities = []
    
    # Register Extruder, Hotbed, and Progress sensors for every printer
    for printer in coordinator.printers:
        entities.append(AnkerMakeTempSensor(coordinator, printer, "Extruder", "nozzle_temp"))
        entities.append(AnkerMakeTempSensor(coordinator, printer, "Hotbed", "hotbed_temp"))
        entities.append(AnkerMakeProgressSensor(coordinator, printer))
    
    async_add_entities(entities, True)


class AnkerMakeTempSensor(CoordinatorEntity, SensorEntity):
    """Representation of an AnkerMake Temperature Sensor."""

    def __init__(self, coordinator, printer, friendly_name, data_key):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.printer = printer
        self.friendly_name = friendly_name
        self.data_key = data_key

        # Important Entity attributes
        self._attr_name = f"{printer.name} {friendly_name} Temperature"
        self._attr_unique_id = f"{printer.sn}_{data_key}"
        self._attr_native_unit_of_measurement = "°C"
        
    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data.get(self.printer.sn, {})
        return data.get(self.data_key)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # True if MQTT is connected and actively supplying data
        return self.coordinator.last_update_success

class AnkerMakeProgressSensor(CoordinatorEntity, SensorEntity):
    """Representation of an AnkerMake Print Progress Sensor."""

    def __init__(self, coordinator, printer):
        super().__init__(coordinator)
        self.printer = printer

        self._attr_name = f"{printer.name} Print Progress"
        self._attr_unique_id = f"{printer.sn}_progress"
        self._attr_native_unit_of_measurement = "%"
        self._attr_icon = "mdi:printer-3d"
        
    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data.get(self.printer.sn, {})
        return data.get("progress")

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success
