import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_COUNTRY

_LOGGER = logging.getLogger(__name__)

# Schema for the Configuration UI
USER_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL): str,
    vol.Required(CONF_PASSWORD): str,
    vol.Required(CONF_COUNTRY, default="US"): vol.In(["US", "EU", "GB", "DE"]), # Expand as necessary
})


class AnkerMakeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AnkerMake."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            from libflagship.logincache import guess_region
            region = guess_region(user_input[CONF_COUNTRY])

            try:
                # We must run synchronous HTTP requests in an executor to avoid blocking HA
                def _verify_login():
                    from libflagship.httpapi import AnkerHTTPPassportApiV2
                    ppapi = AnkerHTTPPassportApiV2(region=region, verify=True)
                    return ppapi.login(email, password)
                
                result = await self.hass.async_add_executor_job(_verify_login)
                
                if result and "auth_token" in result:
                    return self.async_create_entry(
                        title=email,
                        data=user_input,
                    )
                else:
                    errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.error("Failed to authenticate with AnkerMake during setup: %s", e)
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )
