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
    """ Upload a file to the printer and start the print.

    Uses a separate synchronous PPPP connection (like the CLI) to perform
    the P2P file transfer. The FileTransfer.END packet triggers the print.

    Args:
        - app (object): The application object.
        - file (file-like object): The file to upload to the printer.
    """
    import json
    import logging as log
    import time
    import uuid

    from libflagship.pppp import Duid, P2PCmdType, FileTransfer
    from libflagship.ppppapi import AnkerPPPPApi, FileUploadInfo, PPPPState

    config = app.config["config"]
    with config.open() as cfg:
        printer = cfg.printers[app.config["printer_index"]]

    duid = Duid.from_string(printer.p2p_duid)
    ip = printer.ip_addr
    log.info(f"Opening PPPP connection for file transfer to {ip}")

    api = AnkerPPPPApi.open_lan(duid, host=ip)
    api.connect_lan_search()
    api.start()

    try:
        deadline = time.time() + 15
        while api.state != PPPPState.Connected:
            if time.time() > deadline:
                raise ConnectionError("PPPP connection timeout")
            time.sleep(0.1)

        data = file.read()
        user_name = request.headers.get("User-Agent", "ankerctl").split("/")[0]
        fui = FileUploadInfo.from_data(data, file.filename, user_name=user_name, user_id="-", machine_id="-")
        log.info(f"Uploading {fui.size} bytes as {fui.name!r} (md5={fui.md5})")

        api.send_xzyh(str(uuid.uuid4())[:16].encode(), cmd=P2PCmdType.P2P_SEND_FILE)
        log.info("Sending file metadata..")
        api.aabb_request(bytes(fui) + b"\x00", frametype=FileTransfer.BEGIN)
        log.info("BEGIN acknowledged")

        log.info("Sending file contents..")
        blocksize = 1024 * 32
        chunk_count = 0
        for pos, chunk in _split_chunks(data, blocksize):
            api.aabb_request(chunk, frametype=FileTransfer.DATA, pos=pos)
            chunk_count += 1
            if chunk_count % 10 == 0:
                log.info(f"Sent {chunk_count} chunks ({pos + len(chunk)}/{fui.size} bytes)")

        log.info(f"File transfer complete ({chunk_count} chunks), sending END to start print")
        api.aabb_request(b"", frametype=FileTransfer.END)
        log.info("Print job started successfully")
    finally:
        api.stop()


def _split_chunks(data, blocksize):
    for pos in range(0, len(data), blocksize):
        yield pos, data[pos:pos + blocksize]
