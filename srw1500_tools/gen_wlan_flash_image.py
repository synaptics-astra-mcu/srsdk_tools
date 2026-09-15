#!/usr/bin/env python3
"""
Generate a single 1.5MB WLAN flash image with metadata header and FW/NVRAM/CLM payloads.

- For secure FW packages (FW + BL2 + CERT + FW-metadata bundled in a single fw_pkg.bin),
    using the ``--secure`` option the script parses the FW metadata at the end of the FW image
    to find the BL2 and CERT offsets and sizes inside the FW package and adds additional flash
    file entries for BL2 and CERT that point to offsets within inside fw_pkg.bin

- For non-secure images (plain FW.bin without BL2/CERT), omit ``--secure``
    Only FW/NVRAM/CLM entries will be generated.

- Layout is relative to a logical base address 0x38480000 (not stored in the header).
- The first bytes of the 1.5MB image contain wlan_flash_metadata_t as defined in mhd_internal.h.
- FW/NVRAM/CLM/BL2/CERT images are placed at configured offsets, and the header stores their
    offset (from the base address) and size in bytes.

The output binary is exactly 1.5MB (0x00180000 bytes), padded with 0x00 where unused.
"""

import argparse
import os
import struct
import sys

RESERVED_SIZE = 0x00180000  # 1.5MB reserved for WLAN images

WLAN_FLASH_METADATA_MAGIC = 0x574C414E  # 'WLAN'
WLAN_FLASH_METADATA_VERSION = 1

WLAN_FLASH_IMAGE_TYPE_FW = 1
WLAN_FLASH_IMAGE_TYPE_NVRAM = 2
WLAN_FLASH_IMAGE_TYPE_CLM = 3
WLAN_FLASH_IMAGE_TYPE_BL2 = 4
WLAN_FLASH_IMAGE_TYPE_CERT = 5

WLAN_FLASH_MAX_ENTRIES = 6

# Header and entry formats (little-endian uint32 fields)
# NOTE: Must match wlan_flash_metadata_t / wlan_flash_image_entry_t
#       in mhd_internal.h (3 fields per entry: type, offset, size).
HEADER_FMT = "<IIII"  # magic, version, entry_count, reserved
ENTRY_FMT = "<III"    # type, offset, size
HEADER_SIZE = struct.calcsize(HEADER_FMT)
ENTRY_SIZE = struct.calcsize(ENTRY_FMT)
METADATA_SIZE = HEADER_SIZE + WLAN_FLASH_MAX_ENTRIES * ENTRY_SIZE


# FW metadata (inside FW/secure package) layout, must mirror mhd_internal.h
MAX_FW_METADATA_SIZE = 1024
METADATA_MAGIC = bytes([62, 122, 218, 122])  # {62, 122, 218, 122}
METADATA_LEN = 4
METADATA_VER_LEN = 1
METADATA_JUMP_VALUE_LEN = 3
METADATA_TLV_VER_LEN = 2

# TLV type codes (must match enum metadata_type in mhd_internal.h)
METADATA_TYPE_CHIP_DETAILS = 1
METADATA_TYPE_EXCL_MEM_LOCATION = 2
METADATA_TYPE_STARTUP_LOCATION = 3
METADATA_TYPE_NVRAM_LOCATION = 4
METADATA_TYPE_CONS_ADDR = 5
METADATA_TYPE_CLM_BLOB_LOCATION = 8
METADATA_TYPE_BL2_LOCATION = 32
METADATA_TYPE_CERT_LOCATION = 33

# Keep the metadata header at the start; payloads follow contiguously
# in the order FW, then NVRAM, then CLM, with simple alignment.

def align_offset(offset, align):
    return (offset + (align - 1)) & ~(align - 1)


def add_entry(entries, img_type, offset, size):
    if size == 0:
        return
    if offset >= RESERVED_SIZE or offset + size > RESERVED_SIZE:
        raise ValueError(
            f"Image type {img_type}: offset 0x{offset:08X} + size 0x{size:08X} exceeds reserved 0x{RESERVED_SIZE:08X}"
        )
    # Store (type, offset, size) to match wlan_flash_image_entry_t
    entries.append((img_type, offset, size))


def parse_fw_metadata_for_bl2_cert(fw_data):
    """Parse FW metadata to extract BL2/CERT offsets and sizes.

    This mirrors the MHD's logic:
      1. Look at the last 1024 bytes of the FW image.
      2. Verify the metadata magic at the end of that 1 KB.
      3. Read the version and jump value.
      4. Use the jump value to locate the TLV metadata block.
      5. Inside that block, scan for BL2 (type 0x20) and CERT (type 0x21)
         TLVs and extract their offset/size fields.

    Returns a dictionary with optional keys:
      - 'bl2_offset', 'bl2_size'
      - 'cert_offset', 'cert_size'
    Offsets are relative to the start of fw_data.

    If anything looks invalid (no magic, bad jump value, malformed TLV,
    etc.), an empty dictionary is returned.
    """

    result: dict[str, int] = {}

    if len(fw_data) < MAX_FW_METADATA_SIZE:
        return result

    tail = fw_data[-MAX_FW_METADATA_SIZE:]

    # Check FW metadata magic
    magic_in_tail = tail[-METADATA_LEN:]
    if magic_in_tail != METADATA_MAGIC:
        # No metadata present.
        return result

    # Read metadata version and jump value
    version_offset = MAX_FW_METADATA_SIZE - METADATA_LEN - METADATA_VER_LEN
    version_bytes = tail[version_offset:version_offset + METADATA_VER_LEN]
    if len(version_bytes) != METADATA_VER_LEN:
        return result

    jump_offset = MAX_FW_METADATA_SIZE - METADATA_LEN - METADATA_VER_LEN - METADATA_JUMP_VALUE_LEN
    jump_bytes = tail[jump_offset:jump_offset + METADATA_JUMP_VALUE_LEN]
    if len(jump_bytes) != METADATA_JUMP_VALUE_LEN:
        return result

    # Convert the jump value from big-endian bytes to an integer.
    jump_value = 0
    for byte in jump_bytes:
        jump_value = (jump_value << 8) | byte

    # Compute where the TLV metadata block starts inside the last 1KB
    header_size = METADATA_LEN + METADATA_VER_LEN + METADATA_JUMP_VALUE_LEN
    metadata_block_index = header_size + jump_value
    if metadata_block_index >= MAX_FW_METADATA_SIZE:
        # Jump value points outside the 1KB treat as invalid.
        return result

    metadata_block_index = MAX_FW_METADATA_SIZE - metadata_block_index

    # Restrict TLV parsing to the metadata block only
    block = tail[metadata_block_index:]
    block_len = len(block)

    BL2_FIELD_COUNT = 4   # offset, size, load_addr, jump_addr
    CERT_FIELD_COUNT = 3  # offset, size, load_addr

    for pos in range(0, block_len - 4):
        tlv_type = int.from_bytes(block[pos:pos + 2], "big")
        tlv_len = int.from_bytes(block[pos + 2:pos + 4], "big")

        if tlv_type not in (METADATA_TYPE_BL2_LOCATION, METADATA_TYPE_CERT_LOCATION):
            continue

        if tlv_len < METADATA_TLV_VER_LEN or pos + 4 + tlv_len > block_len:
            continue

        content_len = tlv_len - METADATA_TLV_VER_LEN

        # Decide expected field count based on TLV type and content length.
        # The field counts are fixed (4 for BL2, 3 for CERT); the modulus
        # checks ensure the TLV length is consistent with those formats.
        if tlv_type == METADATA_TYPE_BL2_LOCATION:
            if content_len % BL2_FIELD_COUNT != 0:
                continue
            field_count = BL2_FIELD_COUNT
        else:  # CERT_LOCATION
            if content_len % CERT_FIELD_COUNT != 0:
                continue
            field_count = CERT_FIELD_COUNT

        seg_len = content_len // field_count
        start = pos + 4 + METADATA_TLV_VER_LEN
        end = start + content_len
        raw = block[start:end]

        offset_val = int.from_bytes(raw[0:seg_len], "big")
        size_val = int.from_bytes(raw[seg_len:2 * seg_len], "big")

        # Sanity check: offset/size should be inside FW image payload.
        if offset_val + size_val > len(fw_data):
            continue

        if tlv_type == METADATA_TYPE_BL2_LOCATION:
            result["bl2_offset"] = offset_val
            result["bl2_size"] = size_val
        else:
            result["cert_offset"] = offset_val
            result["cert_size"] = size_val

    return result


def write_image(out_path, fw_path, nvram_path=None, clm_path=None, secure=False):
    """Build a 1.5MB WLAN flash image.

    NVRAM handling:
      - Treats the NVRAM file as text.
      - Drops comment lines starting with '#'.
      - Drops empty/whitespace-only lines.
      - Joins remaining lines and replaces '\n' with NUL (0x00),
        matching the packing used by the standalone nvram_comment_remove tool.
    """

    # Read input files
    if not os.path.isfile(fw_path):
        raise FileNotFoundError(f"FW file not found: {fw_path}")
    with open(fw_path, "rb") as f:
        fw_data = f.read()

    nvram_data = b""
    if nvram_path:
        if not os.path.isfile(nvram_path):
            raise FileNotFoundError(f"NVRAM file not found: {nvram_path}")
        # Load NVRAM as text and strip comments/empty lines, then
        # replace newlines with NUL (0x00) as in nvram_comment_remove.py.
        with open(nvram_path, "r") as f:
            lines = f.readlines()

        processed_lines = []
        for i, line in enumerate(lines):
            stripped_line = line.strip()

            # Skip comment lines starting with '#'
            if stripped_line.startswith("#"):
                # If the next line is empty, skip it as well
                if i + 1 < len(lines) and lines[i + 1].strip() == "":
                    continue
                continue

            # Skip empty/whitespace-only lines
            if not stripped_line:
                continue

            processed_lines.append(line)

        modified_text = "".join(processed_lines).replace("\n", "\x00")
        nvram_data = modified_text.encode("utf-8")

    clm_data = b""
    if clm_path:
        if not os.path.isfile(clm_path):
            raise FileNotFoundError(f"CLM file not found: {clm_path}")
        with open(clm_path, "rb") as f:
            clm_data = f.read()

    # Optionally parse FW metadata (secure FW package) to find BL2/CERT
    # offsets/sizes inside the FW image. This is only done when --secure is
    # explicitly requested, so non-secure images are unaffected.
    if secure:
        fw_meta_info = parse_fw_metadata_for_bl2_cert(fw_data)

        # In secure mode we expect the FW package to contain valid BL2 and
        # CERT TLVs. If they are missing, treat this as a error
        has_bl2 = (
            fw_meta_info.get("bl2_offset") is not None
            and fw_meta_info.get("bl2_size") is not None
        )
        has_cert = (
            fw_meta_info.get("cert_offset") is not None
            and fw_meta_info.get("cert_size") is not None
        )
        if not (has_bl2 and has_cert):
            raise ValueError(
                "--secure was requested, but FW metadata in %s does not "
                "contain both BL2 and CERT TLVs" % fw_path
            )
    else:
        fw_meta_info = {}

    # Build metadata entries and compute contiguous layout:
    # [metadata][FW][NVRAM][CLM], in that order.
    entries = []

    # Place FW immediately after metadata, aligned to 0x100.
    fw_offset = align_offset(METADATA_SIZE, 0x100)
    add_entry(entries, WLAN_FLASH_IMAGE_TYPE_FW, fw_offset, len(fw_data))

    # If FW metadata provides BL2/CERT offsets/sizes, emit additional
    # overlapping entries that point into the FW blob.
    bl2_offset_in_pkg = fw_meta_info.get("bl2_offset")
    bl2_size = fw_meta_info.get("bl2_size")
    cert_offset_in_pkg = fw_meta_info.get("cert_offset")
    cert_size = fw_meta_info.get("cert_size")

    if bl2_offset_in_pkg is not None and bl2_size is not None:
        bl2_flash_offset = fw_offset + bl2_offset_in_pkg
        add_entry(entries, WLAN_FLASH_IMAGE_TYPE_BL2, bl2_flash_offset, bl2_size)

    if cert_offset_in_pkg is not None and cert_size is not None:
        cert_flash_offset = fw_offset + cert_offset_in_pkg
        add_entry(entries, WLAN_FLASH_IMAGE_TYPE_CERT, cert_flash_offset, cert_size)

    nvram_offset = None
    clm_offset = None

    if nvram_data:
        nvram_offset = align_offset(fw_offset + len(fw_data), 0x100)
        add_entry(entries, WLAN_FLASH_IMAGE_TYPE_NVRAM, nvram_offset, len(nvram_data))

    if clm_data:
        base = fw_offset + len(fw_data)
        if nvram_data:
            base = nvram_offset + len(nvram_data)
        clm_offset = align_offset(base, 0x100)
        add_entry(entries, WLAN_FLASH_IMAGE_TYPE_CLM, clm_offset, len(clm_data))

    if len(entries) == 0:
        raise ValueError("No images provided to include in flash image")
    if len(entries) > WLAN_FLASH_MAX_ENTRIES:
        raise ValueError("Too many image entries for header")

    # Pack header
    header = struct.pack(
        HEADER_FMT,
        WLAN_FLASH_METADATA_MAGIC,
        WLAN_FLASH_METADATA_VERSION,
        len(entries),
        0,
    )

    # Pack entries (pad to WLAN_FLASH_MAX_ENTRIES with zeros)
    entry_bytes = b""
    for etype, off, size in entries:
        entry_bytes += struct.pack(ENTRY_FMT, etype, off, size)
    # Pad remaining entries
    while len(entry_bytes) < WLAN_FLASH_MAX_ENTRIES * ENTRY_SIZE:
        entry_bytes += struct.pack(ENTRY_FMT, 0, 0, 0)

    if len(header) + len(entry_bytes) > METADATA_SIZE:
        raise AssertionError("Metadata header size mismatch")

    # Initialize full 1.5MB image with 0x00
    image = bytearray(b"\x00" * RESERVED_SIZE)

    # Place metadata at start (offset 0)
    image[0:HEADER_SIZE] = header
    image[HEADER_SIZE:HEADER_SIZE + len(entry_bytes)] = entry_bytes

    # Place FW payload
    fw_offset_in_img = fw_offset
    end = fw_offset_in_img + len(fw_data)
    if end > RESERVED_SIZE:
        raise ValueError("FW image exceeds reserved size")
    image[fw_offset_in_img:end] = fw_data

    # Place NVRAM payload (optional)
    if nvram_data:
        nv_off = nvram_offset
        end = nv_off + len(nvram_data)
        if end > RESERVED_SIZE:
            raise ValueError("NVRAM image exceeds reserved size")
        image[nv_off:end] = nvram_data

    # Place CLM payload (optional)
    if clm_data:
        cl_off = clm_offset
        end = cl_off + len(clm_data)
        if end > RESERVED_SIZE:
            raise ValueError("CLM image exceeds reserved size")
        image[cl_off:end] = clm_data

    # Write final 1.5MB image
    with open(out_path, "wb") as f:
        f.write(image)

    print(f"Generated WLAN flash image: {out_path}")
    print(f"  Size: {len(image)} bytes (0x{len(image):08X})")
    for etype, off, size in entries:
        if etype == WLAN_FLASH_IMAGE_TYPE_FW:
            name = "FW"
        elif etype == WLAN_FLASH_IMAGE_TYPE_NVRAM:
            name = "NVRAM"
        elif etype == WLAN_FLASH_IMAGE_TYPE_CLM:
            name = "CLM"
        elif etype == WLAN_FLASH_IMAGE_TYPE_BL2:
            name = "BL2"
        elif etype == WLAN_FLASH_IMAGE_TYPE_CERT:
            name = "CERT"
        else:
            name = f"TYPE_{etype}"
        print(f"  {name}: offset=0x{off:08X}, size=0x{size:08X}")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Generate 1.5MB WLAN flash image with metadata header")
    p.add_argument("--fw", required=True, help="Path to FW.bin or fw_pkg.bin (for --secure, expects 1024-byte metadata tail)")
    p.add_argument("--nvram", help="Path to nvram.txt (optional)")
    p.add_argument("--clm", help="Path to clm.blob (optional)")
    p.add_argument("--secure", action="store_true", help="Treat FW as secure package and add BL2/CERT entries based on FW metadata")
    p.add_argument("--out", required=True, help="Output flash image path (1.5MB)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        write_image(
            out_path=args.out,
            fw_path=args.fw,
            nvram_path=args.nvram,
            clm_path=args.clm,
            secure=args.secure,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
