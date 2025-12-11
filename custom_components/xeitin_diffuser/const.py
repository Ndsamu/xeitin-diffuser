"""Constants for XEITIN Diffuser integration."""

DOMAIN = "xeitin_diffuser"

# BLE UUIDs
SERVICE_UUID = "0000FFE0-0000-1000-8000-00805F9B34FB"
CHARACTERISTIC_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"

# Protocol constants
HEADER = bytes([0x55, 0xAA])
FOOTER = bytes([0x5A])

# Command bytes
CMD_INIT = 0x47
CMD_GET_STATUS = 0x08
CMD_POWER = 0x07
CMD_KEEPALIVE = 0xA1
CMD_MODE = 0x02          # Set operating mode
CMD_FAN_BOOST = 0x03     # Fan boost on/off
CMD_LOCK = 0x04          # Device lock on/off
CMD_INTENSITY = 0x05     # Set intensity level (1-10)
CMD_TIMER = 0x06         # Set timer duration

# Pre-built packets (verified working)
PACKET_INIT = bytes.fromhex("55AA0147B95A")
PACKET_POWER_ON = bytes.fromhex("55AA04071001E55A")
PACKET_POWER_OFF = bytes.fromhex("55AA04071000E65A")
PACKET_GET_STATUS = bytes.fromhex("55AA0108F85A")
PACKET_KEEPALIVE = bytes.fromhex("55AA01A15F5A")

# Mode packets - Mode I through V (schedules 1-5)
# Format: 55 AA [len=02] [cmd=02] [mode] [checksum] 5A
PACKET_MODE_1 = bytes.fromhex("55AA020201FC5A")  # Mode I
PACKET_MODE_2 = bytes.fromhex("55AA020202FB5A")  # Mode II
PACKET_MODE_3 = bytes.fromhex("55AA020203FA5A")  # Mode III
PACKET_MODE_4 = bytes.fromhex("55AA020204F95A")  # Mode IV
PACKET_MODE_5 = bytes.fromhex("55AA020205F85A")  # Mode V

# Fan boost packets
PACKET_FAN_BOOST_ON = bytes.fromhex("55AA020301FB5A")
PACKET_FAN_BOOST_OFF = bytes.fromhex("55AA020300FC5A")

# Device lock packets
PACKET_LOCK_ON = bytes.fromhex("55AA020401FA5A")
PACKET_LOCK_OFF = bytes.fromhex("55AA020400FB5A")

# Intensity levels 1-10 (format: 55 AA 02 05 [level] [checksum] 5A)
INTENSITY_PACKETS = {
    1: bytes.fromhex("55AA020501F95A"),
    2: bytes.fromhex("55AA020502F85A"),
    3: bytes.fromhex("55AA020503F75A"),
    4: bytes.fromhex("55AA020504F65A"),
    5: bytes.fromhex("55AA020505F55A"),
    6: bytes.fromhex("55AA020506F45A"),
    7: bytes.fromhex("55AA020507F35A"),
    8: bytes.fromhex("55AA020508F25A"),
    9: bytes.fromhex("55AA020509F15A"),
    10: bytes.fromhex("55AA02050AF05A"),
}

# Timer packets (minutes)
TIMER_PACKETS = {
    0: bytes.fromhex("55AA020600F95A"),    # Off
    30: bytes.fromhex("55AA02061EDB5A"),   # 30 min
    60: bytes.fromhex("55AA02063CBB5A"),   # 60 min (1 hr)
    120: bytes.fromhex("55AA0206787B5A"),  # 120 min (2 hrs)
    180: bytes.fromhex("55AA0206B43B5A"),  # 180 min (3 hrs)
}

# Mode names for UI
MODE_OPTIONS = ["Mode I", "Mode II", "Mode III", "Mode IV", "Mode V"]
MODE_PACKETS = [PACKET_MODE_1, PACKET_MODE_2, PACKET_MODE_3, PACKET_MODE_4, PACKET_MODE_5]

# Timer options for UI
TIMER_OPTIONS = ["Off", "30 minutes", "1 hour", "2 hours", "3 hours"]
TIMER_VALUES = [0, 30, 60, 120, 180]

CONF_DEVICE_ADDRESS = "device_address"


def build_packet(cmd: int, data: bytes = b"") -> bytes:
    """Build a protocol packet with proper checksum."""
    length = 1 + len(data)  # cmd byte + data bytes
    payload = bytes([length, cmd]) + data
    checksum = (0x101 - length - cmd - sum(data)) & 0xFF
    return HEADER + payload + bytes([checksum]) + FOOTER
