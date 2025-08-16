
from __future__ import annotations
from struct import pack, unpack_from

# 约定 payload[0] 是 seq，后续是参数

def build_payload(seq: int, *parts: bytes) -> bytes:
    return bytes([seq & 0xFF]) + b"".join(parts)

def enc_fast_drop(seq: int, target_mm: int, speed: int) -> bytes:
    return build_payload(seq, pack("<H", target_mm), pack("<H", speed))

def enc_slow_drop(seq: int, target_mm: int, speed: int) -> bytes:
    return build_payload(seq, pack("<H", target_mm), pack("<H", speed))

def enc_set_param(seq: int, fast_mm: int, slow_mm: int) -> bytes:
    return build_payload(seq, pack("<H", fast_mm), pack("<H", slow_mm))

def dec_ack_status(payload: bytes) -> tuple[int, int, bytes]:
    """返回 (seq, status, data)"""
    if len(payload) < 2:
        return (payload[0] if payload else 0, 0xFF, b"")
    return payload[0], payload[1], payload[2:]

def dec_pose(payload: bytes) -> dict:
    # 示例：seq(1) + status(1) + roll_i16 + pitch_i16 + yaw_i16 (0.01 deg)
    if len(payload) < 2 + 6:
        return {}
    _, status = payload[0], payload[1]
    r, p, y = unpack_from("<hhh", payload, 2)
    return {"status": status, "roll": r/100, "pitch": p/100, "yaw": y/100}
