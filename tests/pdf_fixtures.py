"""Small PDFs authored here for fictional workflow tests; no external examples.

The standard Helvetica name is a PDF built-in font reference, not bundled font
data. Fixtures use ASCII literals and original strings supplied by the test.
"""
from __future__ import annotations

import hashlib
import struct
import zlib


def _literal(value: str) -> bytes:
    return (value.encode("ascii").replace(b"\\", b"\\\\")
            .replace(b"(", b"\\(").replace(b")", b"\\)"))


def _assemble(objects: list[bytes], trailer: bytes = b"") -> bytes:
    raw = bytearray(b"%PDF-1.4\n% independent fictional fixture\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(raw))
        raw.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(raw)
    raw.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        raw.extend(f"{offset:010d} 00000 n \n".encode())
    raw.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R ".encode())
    raw.extend(trailer + f">>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(raw)


def streams_pdf(streams: list[bytes], *, compressed: bool = False,
                image_pages: tuple[int, ...] = (),
                stream_filter: bytes | None = None,
                catalog_extra: bytes = b"", page_extra: bytes = b"",
                extra_objects: tuple[bytes, ...] = ()) -> bytes:
    """One stream per page; adversarial variants remain authored test inputs."""
    kids = " ".join(f"{4 + i * 2} 0 R" for i in range(len(streams)))
    objects = [b"<< /Type /Catalog /Pages 2 0 R " + catalog_extra + b">>",
               f"<< /Type /Pages /Kids [{kids}] /Count {len(streams)} >>".encode(),
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    image_id = 4 + len(streams) * 2
    for index, stream in enumerate(streams):
        image = f" /XObject << /Im0 {image_id} 0 R >>".encode() if index in image_pages else b""
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       b"/Resources << /Font << /F1 3 0 R >>" + image + b" >> "
                       + f"/Contents {5 + index * 2} 0 R ".encode() + page_extra + b" >>")
        filter_name = b" /Filter /FlateDecode" if compressed else b""
        if stream_filter is not None:
            filter_name = b" /Filter " + stream_filter
        content = zlib.compress(stream) if compressed else stream
        objects.append(f"<< /Length {len(content)}".encode() + filter_name
                       + b" >>\nstream\n" + content + b"\nendstream")
    if image_pages:
        objects.append(b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
                       b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\n"
                       b"stream\n\x00\nendstream")
    return _assemble(objects + list(extra_objects))


def text_pdf(pages: list[list[str]], *, compressed: bool = False) -> bytes:
    """Create reproducible fictional ASCII text pages; [] is a blank page."""
    streams = []
    for lines in pages:
        if not lines:
            streams.append(b"")
            continue
        commands = [b"BT /F1 10 Tf 12 TL 36 756 Td"]
        commands.extend(b"(" + _literal(line) + b") Tj T*" for line in lines)
        commands.append(b"ET")
        streams.append(b"\n".join(commands))
    return streams_pdf(streams, compressed=compressed)


def encrypted_pdf(*, empty_password: bool = False) -> bytes:
    """Original RC4/R2 test PDF. This fixture helper is not production crypto."""
    padding = bytes.fromhex("28bf4e5e4e758a4164004e56fffa01082e2e00b6d0683e802f0ca9fe6453697a")

    def padded(value: bytes) -> bytes:
        return (value + padding)[:32]

    def rc4(key: bytes, value: bytes) -> bytes:
        state = list(range(256))
        index = 0
        for position in range(256):
            index = (index + state[position] + key[position % len(key)]) % 256
            state[position], state[index] = state[index], state[position]
        first = second = 0
        output = bytearray()
        for byte in value:
            first = (first + 1) % 256
            second = (second + state[first]) % 256
            state[first], state[second] = state[second], state[first]
            output.append(byte ^ state[(state[first] + state[second]) % 256])
        return bytes(output)

    password = b"" if empty_password else b"fictional-password"
    owner = rc4(hashlib.md5(padded(b"fictional-owner")).digest()[:5], padded(password))
    identifier = b"fictional-pdf-id"
    key = hashlib.md5(padded(password) + owner + struct.pack("<i", -4) + identifier).digest()[:5]
    user = rc4(key, padding)
    stream = b"BT /F1 10 Tf 36 756 Td (Independent fictional encrypted report) Tj ET"
    object_key = hashlib.md5(key + b"\x05\x00\x00\x00\x00").digest()[:10]
    encrypted = rc4(object_key, stream)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>",
        f"<< /Length {len(encrypted)} >>\nstream\n".encode() + encrypted + b"\nendstream",
        b"<< /Filter /Standard /V 1 /R 2 /Length 40 /P -4 /O <" + owner.hex().encode()
        + b"> /U <" + user.hex().encode() + b"> >>",
    ]
    return _assemble(objects, b"/Encrypt 6 0 R /ID [<" + identifier.hex().encode()
                     + b"><" + identifier.hex().encode() + b">] ")
