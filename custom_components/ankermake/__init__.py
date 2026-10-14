import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_COUNTRY, DATA_COORDINATOR

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AnkerMake from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    email = entry.data.get(CONF_EMAIL)
    password = entry.data.get(CONF_PASSWORD)
    country = entry.data.get(CONF_COUNTRY)

    _LOGGER.info(f"Setting up AnkerMake integration for: {email} in region: {country}")

    def _init_ankermake():
        from libflagship.httpapi import AnkerHTTPPassportApiV2, AnkerHTTPAppApiV1
        from libflagship.logincache import guess_region
        from cli.model import Account, Printer
        from libflagship.megajank import pppp_decode_initstring
        from libflagship.util import unhex
        from datetime import datetime

        region = guess_region(country)

        ppapi = AnkerHTTPPassportApiV2(region=region, verify=True)
        login_res = ppapi.login(email, password)
        auth_token = login_res["auth_token"]

        appapi = AnkerHTTPAppApiV1(auth_token=auth_token, region=region, verify=True)
        printers_data = appapi.query_fdm_list()

        account = Account(
            auth_token=auth_token,
            region=region,
            user_id=login_res.get("user_id", ""),
            email=email,
            country=country,
        )
        
        # 3. Create Printer objects
        printers = []
        for pr in printers_data:
            printers.append(Printer(
                id=pr.get("station_id"),
                sn=pr.get("station_sn"),
                name=pr.get("station_name"),
                model=pr.get("station_model"),
                create_time=datetime.fromtimestamp(pr.get("create_time", 0)),
                update_time=datetime.fromtimestamp(pr.get("update_time", 0)),
                mqtt_key=unhex(pr.get("secret_key", "")),
                wifi_mac=pr.get("wifi_mac"),
                ip_addr=pr.get("ip_addr"),
                api_hosts=pppp_decode_initstring(pr.get("app_conn", "")),
                p2p_hosts=pppp_decode_initstring(pr.get("p2p_conn", "")),
                p2p_duid=pr.get("p2p_did"),
                p2p_key="",
            ))
            
        return account, printers

    try:
        account, printers = await hass.async_add_executor_job(_init_ankermake)
    except Exception as e:
        _LOGGER.error("Failed to fetch AnkerMake printers from HTTP API: %s", e)
        return False

    from .coordinator import AnkerMakeCoordinator
    coordinator = AnkerMakeCoordinator(hass, account, printers)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator
    }

    # Forward the setup to the sensor/camera platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # We should cleanly disconnect MQTT clients from the coordinator
        coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        for _, client in coordinator.clients:
            client._mqtt.disconnect()
            
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
