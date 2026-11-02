"""Lossless, bounded deltas for repeated host snapshots, not primary journals.

The first record and every 64th checkpoint remain ordinary JSON objects.
Intermediate records use the previous exact JSON bytes as a Zstandard dictionary.
Decoded bytes, record order and record SHA256 remain identical to the old history.
"""
from __future__ import annotations

import base64
import binascii
try:
    from compression import zstd
except ImportError:  # Python 3.11 and 3.12 use the host's libzstd.
    zstd = None
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path

SCHEMA = 'abyss_machine_snapshot_history_delta_v1'
MAX_CHAIN = 63
MAX_RECORD_BYTES = 64 * 1024 * 1024
MAX_TAIL_BYTES = 16 * 1024 * 1024


class HistoryError(ValueError):
    pass


def _libzstd():
    # Load only when a delta is actually used; ordinary CLI imports stay portable.
    import ctypes
    import ctypes.util

    name = ctypes.util.find_library('zstd')
    if not name:
        raise HistoryError('libzstd is required for snapshot deltas')
    lib = ctypes.CDLL(name)
    void = ctypes.c_void_p
    size = ctypes.c_size_t
    for function, args, result in (
        ('ZSTD_createCCtx', (), void),
        ('ZSTD_createDCtx', (), void),
        ('ZSTD_freeCCtx', (void,), size),
        ('ZSTD_freeDCtx', (void,), size),
        ('ZSTD_compressBound', (size,), size),
        ('ZSTD_compress_usingDict', (void, void, size, void, size, void, size, ctypes.c_int), size),
        ('ZSTD_decompress_usingDict', (void, void, size, void, size, void, size), size),
        ('ZSTD_findFrameCompressedSize', (void, size), size),
        ('ZSTD_isError', (size,), ctypes.c_uint),
    ):
        method = getattr(lib, function)
        method.argtypes, method.restype = args, result
    return lib


def _compress(raw: bytes, previous: bytes) -> bytes:
    if zstd is not None:
        return zstd.compress(raw, level=3, zstd_dict=zstd.ZstdDict(previous, is_raw=True))
    import ctypes
    lib = _libzstd()
    ctx = lib.ZSTD_createCCtx()
    if not ctx:
        raise HistoryError('cannot allocate Zstandard compressor')
    try:
        bound = lib.ZSTD_compressBound(len(raw))
        out = ctypes.create_string_buffer(bound)
        length = lib.ZSTD_compress_usingDict(ctx, out, bound, raw, len(raw), previous, len(previous), 3)
        if lib.ZSTD_isError(length):
            raise HistoryError('cannot compress snapshot delta')
        return out.raw[:length]
    finally:
        lib.ZSTD_freeCCtx(ctx)


def _decompress(frame: bytes, previous: bytes, size: int) -> bytes:
    if zstd is not None:
        try:
            decoder = zstd.ZstdDecompressor(zstd_dict=zstd.ZstdDict(previous, is_raw=True))
            decoded = decoder.decompress(frame, max_length=size + 1)
        except zstd.ZstdError as exc:
            raise HistoryError('invalid snapshot delta frame') from exc
        if not decoder.eof or decoder.unused_data or len(decoded) != size:
            raise HistoryError('snapshot delta size/frame mismatch')
        return decoded
    import ctypes
    lib = _libzstd()
    frame_size = lib.ZSTD_findFrameCompressedSize(frame, len(frame))
    if lib.ZSTD_isError(frame_size) or frame_size != len(frame):
        raise HistoryError('snapshot delta size/frame mismatch')
    ctx = lib.ZSTD_createDCtx()
    if not ctx:
        raise HistoryError('cannot allocate Zstandard decompressor')
    try:
        out = ctypes.create_string_buffer(size + 1)
        length = lib.ZSTD_decompress_usingDict(ctx, out, size + 1, frame, len(frame), previous, len(previous))
        if lib.ZSTD_isError(length) or length != size:
            raise HistoryError('snapshot delta size/frame mismatch')
        return out.raw[:length]
    finally:
        lib.ZSTD_freeDCtx(ctx)


@contextmanager
def maintenance_lock(root: Path, *, exclusive: bool = True):
    root.mkdir(parents=True, exist_ok=True)
    fd = os.open(root / '.snapshot-history.lock', os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o664)
    try:
        if os.fstat(fd).st_uid == os.geteuid():
            os.fchmod(fd, 0o664)
            os.fchown(fd, -1, root.stat().st_gid)
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield
    finally:
        os.close(fd)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class Decoder:
    def __init__(self):
        self.previous: bytes | None = None
        self.chain = 0

    def decode(self, raw: bytes) -> bytes:
        try:
            item = json.loads(raw)
            if not isinstance(item, dict) or item.get('schema') != SCHEMA:
                self.previous, self.chain = raw.strip(), 0
                return raw
            size, chain = item.get('bytes'), item.get('chain')
            if type(size) is not int or not 0 < size <= MAX_RECORD_BYTES:
                raise HistoryError('invalid decoded snapshot size')
            if type(chain) is not int or chain != self.chain + 1 or chain > MAX_CHAIN:
                raise HistoryError('invalid snapshot delta chain')
            if self.previous is None or item.get('base_sha256') != digest(self.previous):
                raise HistoryError('snapshot delta base checksum mismatch')
            encoded = item.get('zstd_base64')
            if not isinstance(encoded, str) or len(encoded) > MAX_RECORD_BYTES * 2:
                raise HistoryError('invalid snapshot delta payload')
            try:
                compressed = base64.b64decode(encoded, validate=True)
                decoded = _decompress(compressed, self.previous, size)
            except binascii.Error as exc:
                raise HistoryError('invalid snapshot delta frame') from exc
            if item.get('sha256') != digest(decoded):
                raise HistoryError('snapshot delta content checksum mismatch')
            value = json.loads(decoded)
            if not isinstance(value, dict) or value.get('schema') == SCHEMA:
                raise HistoryError('decoded snapshot must be a plain object')
            self.previous, self.chain = decoded.strip(), chain
            return decoded
        except (ValueError, TypeError, KeyError) as exc:
            self.previous, self.chain = None, 0
            if isinstance(exc, (HistoryError, json.JSONDecodeError)):
                raise
            raise HistoryError('invalid snapshot delta metadata') from exc


def encode(raw: bytes, previous: bytes | None, chain: int) -> bytes:
    if previous is None or chain >= MAX_CHAIN or not 4096 <= len(raw) <= MAX_RECORD_BYTES:
        return raw
    compressed = _compress(raw, previous)
    wrapped = json.dumps({
        'schema': SCHEMA, 'bytes': len(raw), 'chain': chain + 1,
        'base_sha256': digest(previous), 'sha256': digest(raw),
        'zstd_base64': base64.b64encode(compressed).decode('ascii'),
    }, separators=(',', ':')).encode('ascii')
    return wrapped if len(wrapped) < len(raw) * 0.9 else raw


def decoded_identity(raw: bytes) -> dict:
    """Prove exact legacy source bytes without retaining expanded history in RAM."""
    decoder, checksum = Decoder(), hashlib.sha256()
    size = 0
    for line in raw.splitlines(keepends=True):
        ending = b'\n' if line.endswith(b'\n') else b''
        body = line[:-1] if ending else line
        decoded = decoder.decode(body) if body.strip() else body
        checksum.update(decoded + ending)
        size += len(decoded) + len(ending)
    return {'sha256': checksum.hexdigest(), 'size_bytes': size, 'line_count': len(raw.splitlines())}


def tail_state(fd: int) -> Decoder:
    size = os.fstat(fd).st_size
    state = Decoder()
    if size == 0:
        return state
    if os.pread(fd, 1, size - 1) != b'\n':
        raise HistoryError('snapshot history has an incomplete last record')
    chunk = b''
    cursor = size
    anchor = None
    while cursor > 0 and len(chunk) < MAX_TAIL_BYTES:
        take = min(65536, cursor, MAX_TAIL_BYTES - len(chunk))
        cursor -= take
        chunk = os.pread(fd, take, cursor) + chunk
        lines = chunk.splitlines()
        complete = lines if cursor == 0 else lines[1:]
        tail = []
        for line in reversed(complete):
            if not line.strip():
                continue
            tail.append(line.strip())
            value = json.loads(line)
            if not isinstance(value, dict) or value.get('schema') != SCHEMA:
                anchor = list(reversed(tail))
                break
            if len(tail) > MAX_CHAIN:
                raise HistoryError('snapshot history checkpoint missing')
        if anchor is not None:
            break
    # A very large legacy full record can remain a full checkpoint; never guess a base.
    if anchor is None:
        return state
    for line in anchor:
        state.decode(line)
    return state


def append_snapshot(path: Path, data: dict, *, mode: int = 0o664,
                    ensure_ascii: bool = True, sort_keys: bool = False) -> dict:
    raw = json.dumps(data, ensure_ascii=ensure_ascii, sort_keys=sort_keys).encode('utf-8')
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC, mode)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        state = tail_state(fd)
        encoded = encode(raw, state.previous, state.chain)
        pending = memoryview(encoded + b'\n')
        while pending:
            n = os.write(fd, pending)
            if n <= 0:
                raise OSError('short snapshot append')
            pending = pending[n:]
        return {'raw_bytes': len(raw), 'stored_bytes': len(encoded), 'delta': encoded != raw}
    finally:
        os.close(fd)
