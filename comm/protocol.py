
from __future__ import annotations

class CMD:
    PING = 0x01
    GET_VERSION = 0x10
    START_FAST_DROP = 0x20
    START_SLOW_DROP = 0x21
    LEVEL_AND_LOCK  = 0x22
    READ_FORCES     = 0x30
    READ_POSE       = 0x31
    EMERGENCY_STOP  = 0x40
    SET_PARAM       = 0x50
    SYNC_TIME       = 0x60

def is_ack(cmd: int) -> bool:
    return (cmd & 0x80) != 0

def ack_of(cmd: int) -> int:
    return cmd | 0x80

def is_push(cmd: int) -> bool:
    return cmd >= 0xC0  # 设备上报段
