"""
XEITIN Waterless Diffuser BLE Client Library

Protocol reverse-engineered from Scent Tech iOS app traffic capture.
Device: XEITIN Waterless Diffuser (Amazon B0FLCZRFJL)

Packet Structure:
    55 AA [len] [cmd] [data...] [checksum] 5A
    - 55 AA: Header
    - len: Payload length (cmd + data bytes)
    - cmd: Command type
    - data: Command-specific data
    - checksum: (0x101 - len - sum(data)) & 0xFF
    - 5A: Footer

BLE Characteristic:
    Service UUID: 0000FFE0-0000-1000-8000-00805F9B34FB
    Characteristic UUID: 0000FFE1-0000-1000-8000-00805F9B34FB
    Properties: Read, Write, Write Without Response, Notify
"""

import asyncio
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Callable, List
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

logger = logging.getLogger(__name__)

# BLE UUIDs
SERVICE_UUID = "0000FFE0-0000-1000-8000-00805F9B34FB"
CHARACTERISTIC_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"

# Protocol constants
HEADER = bytes([0x55, 0xAA])
FOOTER = bytes([0x5A])


class Command(IntEnum):
    """Command types for the diffuser protocol."""
    INIT = 0x47          # Initial handshake
    GET_SETTINGS = 0x09  # Request settings
    GET_INFO = 0x51      # Request device info
    KEEPALIVE = 0xA1     # Heartbeat/ACK
    GET_STATUS = 0x08    # Get current status
    TIME_SYNC = 0x06     # Sync device time
    POWER_MODE = 0x07    # Power and mode control
    SCHEDULE = 0x14      # Schedule configuration


class PowerMode(IntEnum):
    """Power/spray modes for the diffuser."""
    MODE_10 = 0x10  # Standard mode
    MODE_12 = 0x12  # Alternative mode (possibly fan boost?)


@dataclass
class DiffuserSchedule:
    """Represents a single schedule (Mode I-V) on the diffuser."""
    mode_index: int      # 0-4 for Mode I-V
    enabled: bool
    start_hour: int      # 0-23
    start_minute: int    # 0-59
    end_hour: int        # 0-23
    end_minute: int      # 0-59
    run_time_sec: int    # Spray duration in seconds
    stop_time_sec: int   # Pause between sprays in seconds
    days: int            # Bitmask: bit 0=Mon, bit 1=Tue, etc.

    @property
    def start_minutes_from_midnight(self) -> int:
        return self.start_hour * 60 + self.start_minute

    @property
    def end_minutes_from_midnight(self) -> int:
        return self.end_hour * 60 + self.end_minute

    @classmethod
    def days_from_list(cls, days: List[str]) -> int:
        """Convert list of day names to bitmask."""
        day_map = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
        result = 0
        for day in days:
            if day.lower()[:3] in day_map:
                result |= (1 << day_map[day.lower()[:3]])
        return result


def _calculate_checksum(data: bytes) -> int:
    """Calculate checksum for packet data (length + command + payload)."""
    return (0x101 - sum(data)) & 0xFF


def _build_packet(cmd: int, data: bytes = b'') -> bytes:
    """Build a complete packet with header, length, command, data, checksum, and footer."""
    length = 1 + len(data)  # command byte + data
    payload = bytes([length, cmd]) + data
    checksum = _calculate_checksum(payload)
    return HEADER + payload + bytes([checksum]) + FOOTER


class XEITINDiffuser:
    """
    BLE client for XEITIN Waterless Diffuser.

    Usage:
        async with XEITINDiffuser("XX:XX:XX:XX:XX:XX") as diffuser:
            await diffuser.power_on()
            await diffuser.set_schedule(...)

    Or manual connection:
        diffuser = XEITINDiffuser("XX:XX:XX:XX:XX:XX")
        await diffuser.connect()
        await diffuser.power_on()
        await diffuser.disconnect()
    """

    def __init__(self, address: str, notification_callback: Optional[Callable] = None):
        """
        Initialize the diffuser client.

        Args:
            address: BLE MAC address of the diffuser (e.g., "E4:66:E5:69:91:81")
            notification_callback: Optional callback for notifications from device
        """
        self.address = address
        self._client: Optional[BleakClient] = None
        self._notification_callback = notification_callback
        self._connected = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None and self._client.is_connected

    @staticmethod
    async def discover(timeout: float = 10.0) -> List[BLEDevice]:
        """
        Discover XEITIN diffusers nearby.

        Returns:
            List of BLE devices with names starting with "Scent-"
        """
        devices = await BleakScanner.discover(timeout=timeout)
        return [d for d in devices if d.name and d.name.startswith("Scent-")]

    async def connect(self) -> bool:
        """Connect to the diffuser."""
        try:
            self._client = BleakClient(self.address)
            await self._client.connect()

            # Subscribe to notifications
            await self._client.start_notify(
                CHARACTERISTIC_UUID,
                self._handle_notification
            )

            self._connected = True
            logger.info(f"Connected to diffuser at {self.address}")

            # Send initialization handshake
            await self._send_command(Command.INIT)
            await asyncio.sleep(0.1)

            return True

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from the diffuser."""
        if self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
            finally:
                self._connected = False
                self._client = None

    def _handle_notification(self, sender: int, data: bytearray):
        """Handle incoming notifications from the diffuser."""
        logger.debug(f"Notification from {sender}: {data.hex()}")
        if self._notification_callback:
            self._notification_callback(bytes(data))

    async def _send_command(self, cmd: Command, data: bytes = b'') -> bool:
        """
        Send a command to the diffuser.

        Args:
            cmd: Command type
            data: Command payload data

        Returns:
            True if command was sent successfully
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to diffuser")

        packet = _build_packet(cmd, data)
        logger.debug(f"Sending: {packet.hex()}")

        try:
            await self._client.write_gatt_char(
                CHARACTERISTIC_UUID,
                packet,
                response=False  # Use Write Without Response
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return False

    async def keepalive(self) -> bool:
        """Send keepalive/heartbeat packet."""
        return await self._send_command(Command.KEEPALIVE)

    async def get_status(self) -> bool:
        """Request current device status."""
        return await self._send_command(Command.GET_STATUS)

    async def power_on(self, mode: PowerMode = PowerMode.MODE_10) -> bool:
        """
        Turn the diffuser on.

        Args:
            mode: Power mode (MODE_10 or MODE_12)
        """
        data = bytes([mode, 0x01, 0x00])
        return await self._send_command(Command.POWER_MODE, data)

    async def power_off(self, mode: PowerMode = PowerMode.MODE_10) -> bool:
        """
        Turn the diffuser off.

        Args:
            mode: Power mode (MODE_10 or MODE_12)
        """
        data = bytes([mode, 0x00, 0x00])
        return await self._send_command(Command.POWER_MODE, data)

    async def set_fan(self, enabled: bool) -> bool:
        """
        Enable or disable the fan boost.

        Note: This appears to use MODE_12 based on capture analysis.
        """
        data = bytes([PowerMode.MODE_12, 0x01 if enabled else 0x00, 0x00])
        return await self._send_command(Command.POWER_MODE, data)

    async def set_schedule(self, schedule: DiffuserSchedule) -> bool:
        """
        Set a schedule (Mode I-V) on the diffuser.

        Args:
            schedule: DiffuserSchedule object with all parameters
        """
        # Build schedule data packet
        # Format based on capture analysis:
        # [mode_idx] [flags] [days?] [00] [start_time_le] [end_time_le] [run_time_le] [stop_time_le] ...

        start_mins = schedule.start_minutes_from_midnight
        end_mins = schedule.end_minutes_from_midnight

        data = bytes([
            schedule.mode_index,
            0x03 if schedule.enabled else 0x02,  # Flags (observed pattern)
            schedule.days | (0x80 if schedule.enabled else 0x00),  # Days + enabled flag
            0x00,
            start_mins & 0xFF,         # Start time low byte
            (start_mins >> 8) & 0xFF,  # Start time high byte
            end_mins & 0xFF,           # End time low byte
            (end_mins >> 8) & 0xFF,    # End time high byte
            schedule.run_time_sec & 0xFF,
            (schedule.run_time_sec >> 8) & 0xFF,
            schedule.stop_time_sec & 0xFF,
            (schedule.stop_time_sec >> 8) & 0xFF,
            0x00, 0x00, 0x00, 0x00,    # Padding/reserved
        ])

        return await self._send_command(Command.SCHEDULE, data)

    async def sync_time(self, timestamp: Optional[int] = None) -> bool:
        """
        Sync device time.

        Args:
            timestamp: Unix timestamp (uses current time if not provided)
        """
        import time
        if timestamp is None:
            timestamp = int(time.time())

        # Time sync format observed: 55AA 0506 [time_bytes] [checksum] 5A
        # The exact format needs more analysis, but this is a starting point
        data = bytes([
            timestamp & 0xFF,
            (timestamp >> 8) & 0xFF,
            (timestamp >> 16) & 0xFF,
            (timestamp >> 24) & 0xFF,
        ])

        return await self._send_command(Command.TIME_SYNC, data)


# Convenience function for quick testing
async def test_connection(address: str) -> bool:
    """Test connection to a diffuser at the given address."""
    try:
        async with XEITINDiffuser(address) as diffuser:
            await diffuser.keepalive()
            print(f"Successfully connected to diffuser at {address}")
            return True
    except Exception as e:
        print(f"Failed to connect: {e}")
        return False


if __name__ == "__main__":
    # Example usage
    import sys

    async def main():
        # Discover devices
        print("Scanning for XEITIN diffusers...")
        devices = await XEITINDiffuser.discover(timeout=10)

        if not devices:
            print("No diffusers found. Make sure device is powered on and not connected to another app.")
            return

        print(f"Found {len(devices)} diffuser(s):")
        for i, device in enumerate(devices):
            print(f"  [{i}] {device.name} ({device.address})")

        if len(sys.argv) > 1:
            address = sys.argv[1]
        else:
            address = devices[0].address
            print(f"\nUsing first found device: {address}")

        # Connect and test
        print(f"\nConnecting to {address}...")
        async with XEITINDiffuser(address) as diffuser:
            print("Connected!")

            # Send keepalive
            print("Sending keepalive...")
            await diffuser.keepalive()
            await asyncio.sleep(0.5)

            # Get status
            print("Requesting status...")
            await diffuser.get_status()
            await asyncio.sleep(0.5)

            print("Test complete!")

    asyncio.run(main())
