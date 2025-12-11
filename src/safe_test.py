#!/usr/bin/env python3
"""
Safe Testing Script for XEITIN Diffuser

This script uses ONLY commands captured from the official app.
It performs read-only operations first, then asks for confirmation
before sending any control commands.

Safety features:
- Only uses exact byte sequences from captured app traffic
- Requires explicit confirmation before power commands
- Displays all sent/received data for verification
- Can be interrupted at any time with Ctrl+C
"""

import asyncio
import sys
from xeitin_diffuser import XEITINDiffuser, DiffuserSchedule, PowerMode

# Captured packets from official app (known safe)
KNOWN_SAFE_PACKETS = {
    "init": bytes.fromhex("55AA0147B95A"),
    "keepalive": bytes.fromhex("55AA01A15F5A"),
    "get_status": bytes.fromhex("55AA0108F85A"),
    "get_info": bytes.fromhex("55AA0151AF5A"),
    "power_on_mode10": bytes.fromhex("55AA04071001E55A"),
    "power_off_mode10": bytes.fromhex("55AA04071000E65A"),
}


class SafeTestDiffuser(XEITINDiffuser):
    """Extended diffuser class with verbose logging for testing."""

    def __init__(self, address: str):
        super().__init__(address, notification_callback=self._log_notification)
        self._received_packets = []

    def _log_notification(self, data: bytes):
        """Log all received packets."""
        print(f"  <- RECEIVED: {data.hex()}")
        self._received_packets.append(data)

    async def send_raw_packet(self, packet: bytes, description: str = "") -> bool:
        """Send a raw packet (for testing captured packets directly)."""
        if not self.is_connected:
            raise ConnectionError("Not connected")

        print(f"  -> SENDING ({description}): {packet.hex()}")

        try:
            from xeitin_diffuser import CHARACTERISTIC_UUID
            await self._client.write_gatt_char(
                CHARACTERISTIC_UUID,
                packet,
                response=False
            )
            return True
        except Exception as e:
            print(f"  !! ERROR: {e}")
            return False


async def safe_test(address: str):
    """Run safe tests with explicit confirmations."""

    print("\n" + "="*60)
    print("XEITIN Diffuser Safe Test Script")
    print("="*60)
    print(f"\nTarget device: {address}")
    print("\nThis script will:")
    print("  1. Connect to the device")
    print("  2. Send read-only commands (safe)")
    print("  3. Ask permission before any control commands")
    print("\nYou can press Ctrl+C at any time to abort.")
    print("="*60)

    input("\nPress Enter to begin connection...")

    diffuser = SafeTestDiffuser(address)

    try:
        # Connect
        print("\n[1/4] Connecting to device...")
        connected = await diffuser.connect()
        if not connected:
            print("Failed to connect. Is the device powered on?")
            print("Is it already connected to the Scent Tech app?")
            return False

        print("Connected successfully!")
        await asyncio.sleep(0.5)

        # Phase 1: Read-only commands
        print("\n[2/4] Sending read-only commands (safe)...")

        print("\n  Sending init handshake...")
        await diffuser.send_raw_packet(KNOWN_SAFE_PACKETS["init"], "init")
        await asyncio.sleep(0.3)

        print("\n  Sending keepalive...")
        await diffuser.send_raw_packet(KNOWN_SAFE_PACKETS["keepalive"], "keepalive")
        await asyncio.sleep(0.3)

        print("\n  Requesting device status...")
        await diffuser.send_raw_packet(KNOWN_SAFE_PACKETS["get_status"], "get_status")
        await asyncio.sleep(0.5)

        print("\n  Requesting device info...")
        await diffuser.send_raw_packet(KNOWN_SAFE_PACKETS["get_info"], "get_info")
        await asyncio.sleep(0.5)

        print("\n" + "-"*40)
        print("Read-only phase complete!")
        print(f"Received {len(diffuser._received_packets)} response packets.")
        print("-"*40)

        # Phase 2: Control commands (with confirmation)
        print("\n[3/4] Power control test (requires confirmation)")
        print("\nWARNING: The next step will send power commands to the device.")
        print("These are the EXACT bytes captured from the official app.")

        response = input("\nDo you want to test power ON/OFF? (yes/no): ").strip().lower()

        if response == "yes":
            print("\n  Sending POWER OFF command...")
            await diffuser.send_raw_packet(KNOWN_SAFE_PACKETS["power_off_mode10"], "power_off")
            await asyncio.sleep(1)

            print("\n  Sending POWER ON command...")
            await diffuser.send_raw_packet(KNOWN_SAFE_PACKETS["power_on_mode10"], "power_on")
            await asyncio.sleep(1)

            print("\n  Sending POWER OFF command (cleanup)...")
            await diffuser.send_raw_packet(KNOWN_SAFE_PACKETS["power_off_mode10"], "power_off")
            await asyncio.sleep(0.5)

            print("\nPower test complete! Did the device respond correctly?")
        else:
            print("Skipping power test.")

        # Summary
        print("\n[4/4] Test Summary")
        print("="*40)
        print(f"Total packets sent: ~6")
        print(f"Total packets received: {len(diffuser._received_packets)}")
        print("\nReceived packet dump:")
        for i, pkt in enumerate(diffuser._received_packets):
            print(f"  {i+1}. {pkt.hex()}")

        print("\n" + "="*40)
        print("Test complete!")
        print("="*40)

        return True

    except KeyboardInterrupt:
        print("\n\nTest aborted by user.")
        return False

    except Exception as e:
        print(f"\nError during test: {e}")
        return False

    finally:
        print("\nDisconnecting...")
        await diffuser.disconnect()
        print("Disconnected.")


async def discover_and_test():
    """Discover devices and run safe test."""

    print("Scanning for XEITIN diffusers (10 seconds)...")
    devices = await XEITINDiffuser.discover(timeout=10)

    if not devices:
        print("\nNo diffusers found!")
        print("\nTroubleshooting:")
        print("  1. Is the diffuser powered on?")
        print("  2. Is it already connected to the Scent Tech app? (Close the app)")
        print("  3. Is Bluetooth enabled on this device?")
        print("  4. Are you within range of the diffuser?")
        return

    print(f"\nFound {len(devices)} diffuser(s):")
    for i, device in enumerate(devices):
        print(f"  [{i}] {device.name} - {device.address}")

    if len(devices) == 1:
        address = devices[0].address
        print(f"\nUsing: {address}")
    else:
        try:
            idx = int(input("\nSelect device number: "))
            address = devices[idx].address
        except (ValueError, IndexError):
            print("Invalid selection.")
            return

    await safe_test(address)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Address provided as argument
        asyncio.run(safe_test(sys.argv[1]))
    else:
        # Discover and test
        asyncio.run(discover_and_test())
