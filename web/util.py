from flask import flash, redirect, request


def flash_redirect(path: str, message: str | None = None, category="info"):
    """
    Flashes a message and redirects the user to the specified path.

    Args:
        - path (str): A string representing the path to redirect the user to.
        - message (str | None): An optional string message to flash to the user.
        - category (str): A string representing the category of the flashed message. 
            Possible values are "info" (default), "danger", "warning", "success".

    Raises:
        - ValueError: If the path parameter is not provided.

    Returns:
        - A Flask redirect object.
    """
    if not path:
        raise ValueError("Redirect path is required")

    if message:
        flash(message, category)

    return redirect(path)


def upload_file_to_printer(app, file):
    """ This function uploads a file to the printer and starts the print.

    Args:
        - app (object): The application object.
        - file (file-like object): The file to upload to the printer.
    """
    import logging as log

    from web.lib.service import RunState

    user_name = request.headers.get("User-Agent", "ankerctl").split("/")[0]

    with app.svc.borrow("filetransfer") as ft:
        ft.send_file(file, user_name)

    log.info(f"File upload complete, sending print start command for {file.filename!r}")
    mq = app.svc.svcs.get("mqttqueue")
    if mq and mq.state == RunState.Running:
        with app.svc.borrow("mqttqueue") as mq:
            mq.client.command({"commandType": 1001, "name": file.filename})
            log.info("Print start command sent")
    else:
        log.warning("MQTT not available, cannot send print start command")
