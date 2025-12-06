"""Unix socket server for receiving hook messages."""

import logging
import os
import socket
import threading
from typing import Callable, Optional

from claude_notify.hook.protocol import decode_hook_message, HookMessage

logger = logging.getLogger(__name__)


class DaemonServer:
    """Unix socket server for daemon."""

    def __init__(
        self,
        socket_path: str,
        message_handler: Callable[[HookMessage], None],
    ):
        self._socket_path = socket_path
        self._handler = message_handler
        self._server: Optional[socket.socket] = None
        self._running = False

    def _ensure_socket_dir(self) -> None:
        """Ensure socket directory exists."""
        socket_dir = os.path.dirname(self._socket_path)
        if socket_dir:
            os.makedirs(socket_dir, exist_ok=True)

    def _cleanup_stale_socket(self) -> None:
        """Remove stale socket file if it exists."""
        try:
            os.unlink(self._socket_path)
        except OSError:
            pass

    def start(self) -> None:
        """Start the server (non-blocking)."""
        self._ensure_socket_dir()
        self._cleanup_stale_socket()

        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self._socket_path)
        self._server.listen(10)
        self._server.settimeout(1.0)
        self._running = True

        logger.info(f"Daemon listening on {self._socket_path}")

    def serve_once(self) -> None:
        """Accept and handle one connection (for testing)."""
        self.start()
        try:
            self._accept_one()
        finally:
            self.shutdown()

    def serve_forever(self) -> None:
        """Accept connections until shutdown."""
        self.start()
        while self._running:
            self._accept_one()

    def _accept_one(self) -> None:
        """Accept and handle one connection."""
        try:
            conn, _ = self._server.accept()
            threading.Thread(
                target=self._handle_connection,
                args=(conn,),
                daemon=True,
            ).start()
        except socket.timeout:
            pass
        except OSError:
            pass  # Server was shut down

    def _handle_connection(self, conn: socket.socket) -> None:
        """Handle a single connection."""
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk

            if data:
                message = decode_hook_message(data.decode("utf-8"))
                self._handler(message)
        except Exception as e:
            logger.warning(f"Error handling connection: {e}")
        finally:
            conn.close()

    def shutdown(self) -> None:
        """Shutdown the server."""
        self._running = False
        if self._server:
            self._server.close()
            self._server = None
        self._cleanup_stale_socket()
