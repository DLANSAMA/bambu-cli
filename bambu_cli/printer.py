import json
import logging
import ssl
import threading
from typing import Optional, Dict, Any

from bambu_cli.protocols import mqtt as mqtt_protocol
from bambu_cli.protocols import ftps as ftps_protocol

logger = logging.getLogger("bambu.printer")

class BambuPrinter:
    """
    A unified client for communicating with a Bambu Lab 3D printer over local network (MQTT & FTPS).
    """

    def __init__(
        self,
        ip: str,
        serial: str,
        access_code: str,
        insecure_tls: bool = False,
        cert_fingerprint: Optional[str] = None,
        simulation_mode: bool = False,
    ):
        self.ip = ip
        self.serial = serial
        self.access_code = access_code
        self.insecure_tls = insecure_tls
        self.cert_fingerprint = cert_fingerprint
        self.simulation_mode = simulation_mode

        # Network timeouts
        self.mqtt_timeout = 5.0
        self.ftps_timeout = 15.0

        self._mqtt_client = None
        self._mqtt_connected = False
        self._mqtt_lock = threading.Lock()

    def connect(self):
        """Establish persistent connections if needed. For now, acts as a verification step."""
        if self.simulation_mode:
            logger.info("🤖 [SIM] Printer connected.")
            return True
        return self.status() is not None

    def disconnect(self):
        """Close any persistent connections."""
        with self._mqtt_lock:
            if self._mqtt_client:
                try:
                    self._mqtt_client.loop_stop()
                    self._mqtt_client.disconnect()
                except Exception:
                    pass
                self._mqtt_client = None
                self._mqtt_connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def send_command(self, payload: str, timeout: Optional[float] = None, retries: int = 2) -> bool:
        """Send a JSON command payload via MQTT."""
        return mqtt_protocol.send_command(self, payload, timeout=timeout, retries=retries)

    def status(self, timeout: Optional[float] = None, retries: int = 2) -> Optional[Dict[str, Any]]:
        """Get the printer status via MQTT."""
        return mqtt_protocol.get_status(self, timeout=timeout, retries=retries)
        
    def get_ftp_client(self, timeout: Optional[float] = None):
        """Context manager to get a connected FTP client."""
        if timeout is None:
            timeout = self.ftps_timeout
        # We can implement pooling here in the future
        client = ftps_protocol._create_raw_ftp(self, timeout=timeout)
        try:
            yield client
        finally:
            try:
                client.quit()
            except Exception:
                pass
            try:
                client.close()
            except Exception:
                pass

    def upload_file(self, local_path: str, remote_path: str, timeout: Optional[float] = None, progress_callback=None) -> bool:
        """Upload a file via FTPS."""
        import os
        import time
        from contextlib import contextmanager
        
        # Enable contextmanager behavior for get_ftp_client
        ctx_get_ftp = contextmanager(self.get_ftp_client)

        filesize = os.path.getsize(local_path)
        max_retries = 3
        uploaded_bytes = 0

        for attempt in range(max_retries + 1):
            try:
                with ctx_get_ftp(timeout=timeout or self.ftps_timeout) as ftp:
                    if attempt == 0:
                        try:
                            ftp.delete(remote_path)
                        except Exception:
                            pass
                    with open(local_path, 'rb') as f:
                        if uploaded_bytes > 0:
                            f.seek(uploaded_bytes)
                        ftp.storbinary(f'STOR {remote_path}', f, blocksize=1048576, rest=uploaded_bytes if uploaded_bytes > 0 else None, callback=progress_callback)
                    return True
            except Exception as e:
                if attempt < max_retries:
                    # Attempt to get remote size for resume
                    try:
                        with ctx_get_ftp(timeout=5) as ftp_check:
                            size = ftp_check.size(remote_path)
                            remote_size = int(size) if size is not None else 0
                            if remote_size == filesize:
                                return True
                            uploaded_bytes = remote_size
                    except Exception:
                        pass
                    time.sleep(5)
                else:
                    logger.error(f"Upload failed: {e}")
                    return False
        return False
        
    def download_file(self, remote_path: str, local_path: str, timeout: Optional[float] = None, progress_callback=None) -> bool:
        """Download a file via FTPS."""
        # Simple download implementation without resume for now
        from contextlib import contextmanager
        ctx_get_ftp = contextmanager(self.get_ftp_client)
        
        try:
            with ctx_get_ftp(timeout=timeout or self.ftps_timeout) as ftp:
                with open(local_path, 'wb') as f:
                    ftp.retrbinary(f'RETR {remote_path}', f.write, blocksize=1048576)
                return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return False
            
    def get_version(self, timeout: Optional[float] = 5.0, retries: int = 1) -> Optional[list]:
        """Get version info via MQTT."""
        return mqtt_protocol.get_version(self, timeout=timeout, retries=retries)
