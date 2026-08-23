import fcntl
import threading
import time
from loguru import logger
from types import TracebackType
from typing import Self, Type

from buttshock import et312

A_BASE = 0x4000
B_BASE = 0x4100
RUNNING_FLAG = 0x4093
READY_VALUE = 0xFF
DEFAULT_READY_TIMEOUT = 5.0

class TensET312:
    """
    Serial interface to an Erostek ET-312 TENS unit via buttshock.
    Based on example code from https://github.com/nannook206/buttshock-py
    """

    def __init__(self, port_str: str = "/dev/ttyUSB0"):
        self._lock = threading.Lock()
        self.conn = None

        with self._lock:
            connected = False
            for _ in range(10):
                try:
                    self.conn = et312.ET312SerialSync(port_str)
                    if self.conn.port.isOpen():
                        fcntl.flock(self.conn.port.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        connected = True
                        break
                except Exception as e:
                    logger.exception("ET-312: Failed to connect, retrying...")
                    time.sleep(.2)
            
            if not connected:
                raise Exception("ET-312: Failed to connect")
            
            try:
                self.conn.perform_handshake()
                # Unused location that gets written
                arewerunning = self._read(RUNNING_FLAG)
                
                if (arewerunning != 42):
                    logger.info("ET-312: Not running, provisioning...")
                    # so let's get it into a blank empty mode. easiest way is calltable 18
                    self._write(0x4078, [0x90]) # mode 90 doesn't exist
                    self._write(0x4070, [18]) # execute mode 90
                    self._wait_ready(0x4070)

                    # Overwrite name of current mode with spaces, then display "FYBot"
                    self._write(0x4180, [0x64])
                    self._write(0x4070, [0x15])
                    self._wait_ready(0x4070)
                    for pos, char in enumerate('FYBot'):
                        self._write(0x4180, [ord(char),pos+9])
                        self._write(0x4070, [0x13])
                        self._wait_ready(0x4070)

                    for base in [A_BASE, B_BASE]:
                        self._write(base+0xa8, [0,0]) # don't increment channel intensity
                        self._write(base+0xa5, [128]) # intensity mod value = min
                        self._write(base+0xac, [0]) # no select
                    
                        self._write(base+0xb1, [0]) # rate        
                        self._write(base+0xae, [0x64]) # freq mod
                        self._write(base+0xb5, [4]) # select normal parms

                        self._write(base+0xb7, [0xc8]) # width mod value
                        self._write(base+0xba, [0]) # width mod value        
                        self._write(base+0xbe, [4]) # select normal parms

                        self._write(base+0x9c, [255]) # ramp off
                        
                    self._write(RUNNING_FLAG,[42]) # we're provisioned

            except Exception:
                logger.exception("ET-312: Failed to provision")
                raise

    def _read(self, address: int) -> int:
        try:
            return self.conn.read(address)
        except Exception:
            logger.exception(f"ET-312: Failed to read from {address:#x}")
            raise

    def _write(self, address: int, content: list[int]) -> None:
        try:
            self.conn.write(address, content)
        except Exception:
            logger.exception(f"ET-312: Failed to write to {address:#x}")
            raise

    def _wait_ready(
        self, address: int = 0x4070, timeout: float = DEFAULT_READY_TIMEOUT
    ) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._read(address) == READY_VALUE:
                return
            time.sleep(0.01)
        raise TimeoutError(
            f"ET-312: Timed out waiting for ready ({READY_VALUE:#x}) at {address:#x}"
        )
    
    def set(self, channel: str, level: int) -> None:
        if level < 0 or level > 127:
            logger.warning(f"ET-312: Level out of bounds: {level}, clamping to 0-127")
            level = max(0, min(127, level))
        if channel.lower() == "a":
            base = A_BASE
        elif channel.lower() == "b":
            base = B_BASE
        else:
            logger.error(f"ET-312: Invalid channel: {channel}")
            return
        
        level += 128 # Normalizing range

        with self._lock:
            if not self.conn:
                logger.error(f"ET-312: Not connected")
                return
            self._write(base+0xac, [0]) # no select
            self._write(base+0xa8, [0, 0])   # rate, direction
            self._write(base+0xa5, [level])
            
    def close(self) -> None:
        with self._lock:
            if (self.conn):
                self.conn.reset_key()
                self.conn.close()
                self.conn = None
 
    def __enter__(self) -> Self:
        return self
    
    def __exit__(self, exc_type: Type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool:
        self.close()
        return False