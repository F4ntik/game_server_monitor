import logging
from PyQt6.QtCore import QObject, pyqtSignal
from ping3 import ping, PingError

class PingWorker(QObject):
    """Рабочий поток для выполнения ping-запросов."""
    ping_result = pyqtSignal(int)
    ping_failed = pyqtSignal()

    def __init__(self, address):
        """Инициализирует PingWorker с заданным адресом.

        :param address: Адрес для выполнения ping-запроса.
        """
        super().__init__()
        self.address = address

    def run(self):
        """Запускает ping-запрос к заданному адресу и передает результат."""
        try:
            if not self.address: # Ensure address is not None or empty
                logging.error("PingWorker.run() called with no address.")
                self.ping_failed.emit()
                return

            response = ping(self.address, timeout=2) # ping3.ping call, unit 's'

            # ping3 returns: delay (float in s), False (timeout), or None (error)
            if response is not None and response is not False: # Check for actual delay value
                self.ping_result.emit(int(response * 1000)) # Convert to ms
            else:
                if response is False: # Explicitly a timeout from ping3
                    logging.warning(f"Ping timed out for address {self.address} after 2 seconds.")
                elif response is None: # Other errors like host unknown (can also raise PingError)
                     logging.warning(f"Ping returned None (possibly host unknown or other network error) for address {self.address}.")
                # else: # Should not happen based on ping3 docs if strictly None/False/float
                #      logging.warning(f"Ping returned unexpected value '{response}' for address {self.address}.")
                self.ping_failed.emit()
        except PingError as e: # Specific exception from ping3
            logging.error(f"Ping failed for address {self.address} with PingError: {e}. This could be due to DNS issues, network configuration, or permissions (e.g., needing root/CAP_NET_RAW for ICMP).")
            self.ping_failed.emit()
        except Exception as e: # Catch any other unexpected error during ping process
            logging.error(f"Unexpected exception in PingWorker for address {self.address}: {e}", exc_info=True) # Add exc_info for traceback
            self.ping_failed.emit()
