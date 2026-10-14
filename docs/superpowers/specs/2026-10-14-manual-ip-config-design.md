# Manual Printer IP Address Configuration

## Overview

Add the ability to manually set the printer IP address from the web UI setup page. Replaces the current "Update Printer IP Addresses" card with a combined scan + manual entry form.

## Current Behavior

The setup page has an "Update Printer IP Addresses" card with a single button that:
1. POSTs to `/api/ankerctl/config/updateip`
2. Triggers a LAN broadcast search
3. Updates `default.json` with found IPs
4. Redirects to internal service reload

If the printer isn't found (different network, firewall, etc.), there is no way to manually enter the IP.

## New Behavior

### UI

The card is renamed to "Printer IP Address" and contains:
- A text input field showing the current IP (pre-filled from `printer.ip_addr`, blank if none)
- A "Scan for Printer" button
- A "Save" button

### Scan Flow

1. User clicks "Scan for Printer"
2. JavaScript sends a `fetch` POST to `/api/ankerctl/config/updateip` with `X-Requested-With: XMLHttpRequest` header
3. Backend performs the same LAN broadcast search as before
4. Instead of redirecting, returns JSON:
   - `{"found": true, "ip": "192.168.1.42"}` — printer found, IP written to config
   - `{"found": false, "message": "No printers responded..."}` — not found
5. JavaScript updates the input field with the found IP (or leaves it unchanged)
6. JavaScript shows a success/warning flash message

### Save Flow

1. User types an IP address into the field (or accepts the scanned value)
2. User clicks "Save"
3. Form POSTs to new endpoint `/api/ankerctl/config/setip` with `ip` field
4. Backend validates the IP is a valid IPv4 address
5. Backend writes the IP to `default.json` via `config.modify()`
6. Backend redirects to internal service reload (same as existing scan flow)

## Backend Changes

### Modified: `/api/ankerctl/config/updateip`

Add XHR detection at the top of the handler:

```python
if request.headers.get("X-Requested-With") == "XMLHttpRequest":
    # Return JSON instead of redirect
    try:
        found_printers, updated_printers = web.config.printer_discovery.search(config)
    except OSError as err:
        return jsonify({"found": False, "message": web.config.search_error_message(err)})
    
    if found_printers and updated_printers:
        # Get the IP for the current printer index
        with config.open() as cfg:
            ip = cfg.printers[app.config["printer_index"]].ip_addr
        return jsonify({"found": True, "ip": ip})
    
    return jsonify({"found": False, "message": "No printers responded within timeout."})
```

The existing redirect behavior is preserved for non-XHR requests (backwards compatible).

### New: `/api/ankerctl/config/setip`

```python
@app.post("/api/ankerctl/config/setip")
def app_api_ankerctl_config_set_ip():
    ip = request.form.get("ip", "").strip()
    
    # Validate IPv4
    import ipaddress
    try:
        ipaddress.IPv4Address(ip)
    except (ipaddress.AddressValueError, ValueError):
        return web.util.flash_redirect(url_for('app_root'), f"Invalid IP address: {ip}", "danger")
    
    config = app.config["config"]
    printer_index = app.config["printer_index"]
    
    with config.modify() as cfg:
        if printer_index >= len(cfg.printers):
            return web.util.flash_redirect(url_for('app_root'), "No printer configured", "danger")
        cfg.printers[printer_index].ip_addr = ip
    
    return app_api_ankerctl_server_internal_reload(f"Printer IP set to {ip}")
```

## Frontend Changes

### Modified: `static/tabs/setup.html`

Replace the existing "Update Printer IP Addresses" form (lines 98-122) with:

```html
{% if printer %}
<div class="card mb-3">
    <div class="card-header fs-4">Printer IP Address</div>
    <div class="card-body">
        <form id="config-set-printer-ip" action="{{ url_for('app_api_ankerctl_config_set_ip') }}" method="POST">
            <div class="input-group mb-3">
                <div class="input-group-text">IP Address</div>
                <input class="form-control" type="text" id="printerIpInput"
                       name="ip" value="{{ printer.ip_addr or '' }}"
                       placeholder="e.g. 192.168.1.42" />
            </div>
            <div class="d-flex gap-2">
                <button type="button" class="btn btn-secondary" id="scan-printer-btn">
                    {{ macro.bi_icon("arrow-clockwise", "Scan for Printer") }}
                </button>
                <button type="submit" class="btn btn-primary">
                    {{ macro.bi_icon("check-lg", "Save") }}
                </button>
            </div>
        </form>
    </div>
</div>
{% endif %}
```

### Modified: `static/ankersrv.js`

Add scan handler:

```javascript
$("#scan-printer-btn").on("click", function () {
    const btn = $(this).prop("disabled", true);
    fetch("/api/ankerctl/config/updateip", {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest" }
    })
    .then(resp => resp.json())
    .then(data => {
        if (data.found) {
            $("#printerIpInput").val(data.ip);
            flash_message(`Found printer at ${data.ip}`, "success");
        } else {
            flash_message(data.message || "Printer not found", "warning");
        }
    })
    .catch(() => flash_message("Scan failed", "danger"))
    .finally(() => btn.prop("disabled", false));
});
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Scan: printer found | Field updated, success flash |
| Scan: no response | Warning flash, field unchanged |
| Scan: network error (macOS privacy) | Warning flash with platform-specific hint |
| Save: invalid IP format | Danger flash, no redirect |
| Save: no printer configured | Danger flash, no redirect |
| Save: valid IP | IP written, services reloaded, success flash |

## Testing

- Unit test for `/api/ankerctl/config/setip` with valid/invalid IPs (using Flask test client)
- Unit test for `/api/ankerctl/config/updateip` XHR mode returning JSON (mocking `printer_discovery.search`)
- Existing tests for the non-XHR redirect path remain unchanged

## Files Modified

- `web/__init__.py` — modify `updateip` handler, add `setip` handler
- `static/tabs/setup.html` — replace IP update form
- `static/ankersrv.js` — add scan button handler
