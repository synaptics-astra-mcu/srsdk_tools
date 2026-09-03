#!/usr/bin/env python3
import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List
from shutil import which

# Shared config lives alongside this script, directly under srw1500_tools/, so
# both the RAM and flash generators use a single srw1500_image_gen_config.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import srw1500_image_gen_config


@dataclass
class ElfSection:
    name: str
    section_type: str
    address: int
    size: int
    flags: str


def run_cmd(cmd: List[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def resolve_tool(user_value: str, candidates: List[str], tool_name: str) -> str:
    # If user passed an explicit tool path/name, honor it.
    if user_value:
        resolved = which(user_value) if os.path.sep not in user_value else user_value
        if resolved and os.path.exists(resolved):
            return resolved
        if os.path.sep not in user_value:
            return user_value
        raise FileNotFoundError(f"{tool_name} not found: {user_value}")

    for candidate in candidates:
        resolved = which(candidate)
        if resolved:
            return resolved

    raise FileNotFoundError(
        f"Unable to find {tool_name}. Tried: {', '.join(candidates)}"
    )


def get_sections(elf_path: str, objdump_bin: str) -> List[ElfSection]:
    """
    Extracts sections from ELF file using objdump -h, filtering for CODE and DATA sections.
    Follows the same logic as Services/utils.py:parse_objdump_output for consistency.
    """
    output = run_cmd([objdump_bin, "-h", elf_path])

    sections: List[ElfSection] = []

    # objdump -h output has header lines, start parsing from line 5
    lines = output.splitlines()[5:]

    # Process two lines at a time: section_info and section_attr
    for i in range(0, len(lines) - 1, 2):
        section_info = lines[i].split()
        section_attr = lines[i + 1].split()

        # Parse section_info line
        if len(section_info) < 5:
            continue

        _, name, size, _, address = section_info[:5]

        # Skip EMPTY sections
        if any('EMPTY' in element for element in section_info):
            continue

        # Only include sections with CODE or DATA flags
        if ('CODE' in section_attr) or ('DATA' in section_attr):
            sections.append(
                ElfSection(
                    name=name,
                    section_type="PROGBITS",
                    address=int(address, 16),
                    size=int(size, 16),
                    flags="",
                )
            )

    return sections


def resolve_signing_key_paths(args) -> tuple[str, str, bool]:
    if args.private_key:
        private_key_path = os.path.abspath(args.private_key)
    else:
        private_key_path = os.path.join(os.path.dirname(__file__), srw1500_image_gen_config.SPK_PRIVKEY)

    if args.public_key:
        public_key_path = os.path.abspath(args.public_key)
    else:
        public_key_path = os.path.join(os.path.dirname(__file__), srw1500_image_gen_config.SPK_PUBKEY)

    has_signing_keys = os.path.isfile(private_key_path) and os.path.isfile(public_key_path)
    return private_key_path, public_key_path, has_signing_keys


def sha512_bytes(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sign_with_private_key(openssl_bin: str, private_key: str, data_file: str) -> bytes:
    result = subprocess.run(
        [openssl_bin, "pkeyutl", "-sign", "-inkey", private_key, "-in", data_file],
        check=True,
        capture_output=True,
    )
    return result.stdout


def extract_r_s_from_signature(openssl_bin: str, der_signature_bytes: bytes) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(der_signature_bytes)
        tmp_file_path = tmp_file.name

    try:
        result = subprocess.run(
            [openssl_bin, "asn1parse", "-in", tmp_file_path, "-inform", "DER"],
            capture_output=True,
            text=True,
            check=True,
        )

        hex_data = []
        for line in result.stdout.strip().splitlines():
            if "INTEGER" in line:
                colon_index = line.rfind(":")
                if colon_index != -1:
                    hex_val = line[colon_index + 1 :].strip()
                    hex_data.append(hex_val)

        if len(hex_data) < 2:
            raise ValueError("Failed to extract R and S from DER signature")

        r, s = hex_data[0], hex_data[1]
        return bytes.fromhex(r + s)
    finally:
        os.remove(tmp_file_path)


def build_opcode_header(opcode: List[int], packet_len: int) -> bytes:
    # Kept for backward compatibility in case this helper is referenced elsewhere.
    # New flow uses build_opcode_header_v2.
    header = bytearray()
    header.extend(list(srw1500_image_gen_config.SYNC_1))
    header.extend(list(srw1500_image_gen_config.SYNC_2))
    header.extend(list(srw1500_image_gen_config.SRV_ID))
    header.extend(opcode)
    header.extend(packet_len.to_bytes(4, byteorder="little"))
    header.extend(list(srw1500_image_gen_config.zero_pad_24_bytes))
    return bytes(header)


def build_opcode_header_v2(
    opcode: List[int],
    num_words_hdr: int,
    num_words_body: int,
    exe_addr_body: int,
    im_addr_hdr: int,
    img_type_word: int,
    msg_hdr_flags_word: int,
    entry_addr: int = 0,
    is_first_section: bool = False,
) -> bytes:
    # AP CMD header (32 bytes, 8 words) matching reference implementation:
    # 1) SYNC word (bytes 0-3)
    # 2) Entry point for 1st section, else zeros (bytes 4-7)
    # 3) u32_num_words_hdr (bytes 8-11)
    # 4) u32_num_words_body (bytes 12-15)
    # 5) u32_exe_addr_body (bytes 16-19)
    # 6) u32_im_addr_hdr (bytes 20-23)
    # 7) u32_img_type (bytes 24-27)
    # 8) u32_msg_hdr_flags (bytes 28-31)
    header = bytearray()

    # SYNC word carries sync + service-id + opcode
    sync_word = (
        list(srw1500_image_gen_config.SYNC_1)
        + list(srw1500_image_gen_config.SYNC_2)
        + list(srw1500_image_gen_config.SRV_ID)
        + opcode
    )
    header.extend(sync_word)

    # Entry point for first section, or zeros otherwise
    if is_first_section:
        header.extend(entry_addr.to_bytes(4, byteorder="little"))
    else:
        header.extend((0).to_bytes(4, byteorder="little"))

    # Word counts and addresses
    header.extend(num_words_hdr.to_bytes(4, byteorder="little"))
    header.extend(num_words_body.to_bytes(4, byteorder="little"))
    header.extend(exe_addr_body.to_bytes(4, byteorder="little"))
    header.extend(im_addr_hdr.to_bytes(4, byteorder="little"))

    # Image type (as integer) and flags
    header.extend(img_type_word.to_bytes(4, byteorder="little"))
    header.extend(msg_hdr_flags_word.to_bytes(4, byteorder="little"))

    if len(header) != 32:
        raise ValueError(f"Invalid opcode header size: {len(header)}, expected 32")

    return bytes(header)


def build_run_command(entry_addr: int) -> bytes:
    # 32-byte run command:
    # 0..3   sync word with OPCODE_RUN_FW_IMG
    # 4..7   reserved
    # 8..11  jump address
    # 12..31 reserved
    header = bytearray()
    header.extend(list(srw1500_image_gen_config.SYNC_1))
    header.extend(list(srw1500_image_gen_config.SYNC_2))
    header.extend(list(srw1500_image_gen_config.SRV_ID))
    header.extend(list(srw1500_image_gen_config.OPCODE_RUN_FW_IMG))
    header.extend((0).to_bytes(4, byteorder="little"))
    header.extend(entry_addr.to_bytes(4, byteorder="little"))
    header.extend(bytes(srw1500_image_gen_config.zero_pad_24_bytes[:20]))

    if len(header) != srw1500_image_gen_config.BOOT_COMMAND_SIZE_BYTES:
        raise ValueError(
            f"Invalid run command size: {len(header)}, "
            f"expected {srw1500_image_gen_config.BOOT_COMMAND_SIZE_BYTES}"
        )

    return bytes(header)

def build_image_header_for_section(
    payload: bytes,
    image_type_word: List[int],
    destination_addr_word: List[int],
    entry_addr: int,
    private_key_path: str,
    has_signing_keys: bool,
    openssl_bin: str,
    temp_dir: str,
) -> bytes:
    image_header = bytearray()
    sign_img_sha256_array = bytearray()

    image_signature_size = srw1500_image_gen_config.SECURED_SIGNATURE_SIZE

    # Match srw1500_image_gen.py length behavior exactly.
    # image_len = image body + HEADER_SIZE constant
    image_len = len(payload) + srw1500_image_gen_config.HEADER_SIZE
    image_len_le = image_len.to_bytes(4, byteorder="little")

    # Image ID (4)
    image_header.extend(list(image_type_word))
    sign_img_sha256_array.extend(list(image_type_word))

    # Image Format Version (4)
    image_header.extend(list(srw1500_image_gen_config.IMG_VER_APP_12_15))
    sign_img_sha256_array.extend(list(srw1500_image_gen_config.IMG_VER_APP_12_15))

    # Length (4)
    image_header.extend(image_len_le)
    sign_img_sha256_array.extend(image_len_le)

    # IV (16)
    image_header.extend(list(srw1500_image_gen_config.CIPHER_20_35))
    sign_img_sha256_array.extend(list(srw1500_image_gen_config.CIPHER_20_35))

    # Checksum (64): SHA-512 over section payload (same as srw1500_image_gen.py)
    payload_sha512 = sha512_bytes(payload)
    image_header.extend(payload_sha512)
    sign_img_sha256_array.extend(payload_sha512)

    # SegID (4)
    image_header.extend(list(srw1500_image_gen_config.SEG_ID_64_67))
    sign_img_sha256_array.extend(list(srw1500_image_gen_config.SEG_ID_64_67))

    # Version (4)
    image_header.extend(list(srw1500_image_gen_config.VER_68_71))
    sign_img_sha256_array.extend(list(srw1500_image_gen_config.VER_68_71))

    # Production_Image_Flag (4)
    image_header.extend(list(srw1500_image_gen_config.PRODUCTION_FLAG))
    sign_img_sha256_array.extend(list(srw1500_image_gen_config.PRODUCTION_FLAG))

    # Reserved (4)
    image_header.extend(list(srw1500_image_gen_config.RFU_72_75))
    sign_img_sha256_array.extend(list(srw1500_image_gen_config.RFU_72_75))

    # Destination address (4) + entry point (4), same location/fill style as srw1500_image_gen.py
    image_header.extend(destination_addr_word)
    sign_img_sha256_array.extend(destination_addr_word)
    entry_bytes = list(entry_addr.to_bytes(4, byteorder="little"))
    image_header.extend(entry_bytes)
    sign_img_sha256_array.extend(entry_bytes)

    # SHA-256 over sign_img_sha256_array and ECDSA sign with provided private key.
    sha256_digest = sha256_bytes(sign_img_sha256_array)
    digest_file = os.path.join(temp_dir, "section_sha256.bin")
    with open(digest_file, "wb") as f:
        f.write(sha256_digest)

    if has_signing_keys:
        der_sig = sign_with_private_key(openssl_bin, private_key_path, digest_file)
        rs_sig = extract_r_s_from_signature(openssl_bin, der_sig)

        if len(rs_sig) > image_signature_size:
            raise ValueError("RS signature length exceeds SECURED_SIGNATURE_SIZE")
        signature_padded = rs_sig + b"\x00" * (image_signature_size - len(rs_sig))
    else:
        signature_padded = b"\x00" * image_signature_size

    image_header.extend(signature_padded)

    return bytes(image_header)


def get_entry_point_address(elf_path: str, readelf_bin: str) -> int:
    output = run_cmd([readelf_bin, "-h", elf_path])
    for line in output.splitlines():
        if srw1500_image_gen_config.ENTRY_POINT_ADDRESS in line:
            for token in line.split():
                if token.startswith("0x"):
                    return int(token, 16)
    raise ValueError("Failed to extract ELF entry point address")


def align_to_word(data: bytes) -> bytes:
    rem = len(data) % 4
    if rem == 0:
        return data
    return data + (b"\x00" * (4 - rem))


def get_payload_for_section(
    elf_path: str,
    section_name: str,
    objcopy_bin: str,
    temp_dir: str,
) -> bytes:
    dump_path = os.path.join(temp_dir, f"section_{section_name.replace('/', '_')}.bin")
    try:
        subprocess.run(
            [objcopy_bin, f"--dump-section", f"{section_name}={dump_path}", elf_path],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"WARN: Skipping section {section_name} (objcopy dump failed): "
            f"{exc.stderr.strip() if exc.stderr else exc}"
        )
        return b""

    if not os.path.exists(dump_path):
        print(f"WARN: Skipping section {section_name} (no dumped payload file)")
        return b""

    with open(dump_path, "rb") as f:
        return f.read()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate consolidated SRAM image from ELF sections with per-section "
            "opcode header + signed image header + payload"
        )
    )
    parser.add_argument("-e", "--elf", required=True, help="Input ELF file")
    parser.add_argument(
        "-a",
        "--app_elf",
        default="",
        help="Application ELF file used to extract entry point (default: --elf)",
    )
    parser.add_argument(
        "-private",
        "--private_key",
        default="",
        help="Private key PEM file path (e.g. priv_4.pem)",
    )
    parser.add_argument(
        "-public",
        "--public_key",
        default="",
        help="Public key PEM file path (e.g. pub_4.pem)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="",
        help="Output consolidated binary file",
    )
    parser.add_argument(
        "-i",
        "--image_type",
        choices=["APP", "APBL"],
        default="APP",
        help="Image type used for opcode and image-type word",
    )
    parser.add_argument(
        "--openssl",
        default="",
        help="openssl executable path (default: openssl)",
    )
    parser.add_argument(
        "--readelf",
        default="",
        help="readelf executable path (default: readelf)",
    )
    parser.add_argument(
        "--objdump",
        default="",
        help="objdump executable path (default: objdump)",
    )
    parser.add_argument(
        "--objcopy",
        default="",
        help="objcopy executable path (default: objcopy)",
    )

    args = parser.parse_args()

    elf_path = os.path.abspath(args.elf)
    app_elf_path = os.path.abspath(args.app_elf) if args.app_elf else elf_path
    private_key_path, public_key_path, has_signing_keys = resolve_signing_key_paths(args)
    out_path = os.path.abspath(args.output)

    if not os.path.exists(elf_path):
        print(f"ERROR: ELF not found: {elf_path}")
        return 2
    if not os.path.exists(app_elf_path):
        print(f"ERROR: App ELF not found: {app_elf_path}")
        return 2
    if has_signing_keys:
        print(f"Using private key: {private_key_path}")
        print(f"Using public key: {public_key_path}")
    else:
        print("Private/public key not found, skipping signing.")

    try:
        openssl_bin = resolve_tool(args.openssl, ["openssl"], "openssl")
        readelf_bin = resolve_tool(
            args.readelf,
            ["arm-none-eabi-readelf", "readelf"],
            "readelf",
        )
        objdump_bin = resolve_tool(
            args.objdump,
            ["arm-none-eabi-objdump", "objdump"],
            "objdump",
        )
        objcopy_bin = resolve_tool(
            args.objcopy,
            ["arm-none-eabi-objcopy", "objcopy"],
            "objcopy",
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    if args.image_type == "APBL":
        opcode = list(srw1500_image_gen_config.OPCODE_DWNLD_SCR_IMG_DEC_IP)
        opcode_image_type = srw1500_image_gen_config.FW_M52_IMAGE_TYPE
        image_type_word = list(srw1500_image_gen_config.IMG_TYPE_APBL_8_11)
        destination_addr_word = list(srw1500_image_gen_config.DESTINATION_ADDRESS_APBL)
        header_addr_word = list(srw1500_image_gen_config.BOOTLOADER_ENTRY_POINT)
    else:
        opcode = list(srw1500_image_gen_config.OPCODE_DWNLD_SCR_IMG_DEC_IP)
        opcode_image_type = srw1500_image_gen_config.FW_M52_IMAGE_TYPE
        image_type_word = list(srw1500_image_gen_config.IMG_TYPE_APP_8_11)
        destination_addr_word = list(srw1500_image_gen_config.DESTINATION_ADDRESS_APP)
        header_addr_word = list(srw1500_image_gen_config.DESTINATION_HEADER_ADDRESS_APP)

    try:
        elf_entry_addr = get_entry_point_address(app_elf_path, readelf_bin)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    sections = get_sections(elf_path, objdump_bin)
    if not sections:
        print("ERROR: No file-backed sections found in ELF")
        return 1

    packet_count = 0
    bytes_written = 0

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    packed_sections = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        for sec in sections:
            payload = get_payload_for_section(elf_path, sec.name, objcopy_bin, tmp_dir)
            if not payload:
                # Skip sections that objcopy materializes as empty.
                continue

            payload_aligned = align_to_word(payload)

            image_header = build_image_header_for_section(
                payload=payload_aligned,
                image_type_word=image_type_word,
                destination_addr_word=destination_addr_word,
                entry_addr=elf_entry_addr,
                private_key_path=private_key_path,
                has_signing_keys=has_signing_keys,
                openssl_bin=openssl_bin,
                temp_dir=tmp_dir,
            )

            expected_hdr_bytes = srw1500_image_gen_config.SUM_OF_SECURITY_HEADER_AND_SIGNATURE
            if len(image_header) != expected_hdr_bytes:
                raise ValueError(
                    f"Unexpected image header size: {len(image_header)} != {expected_hdr_bytes}"
                )

            num_words_hdr = len(image_header) // 4
            num_words_body = len(payload_aligned) // 4
            exe_addr_body = sec.address
            im_addr_hdr = int.from_bytes(bytes(header_addr_word), byteorder="little")

            packed_sections.append(
                (sec, payload_aligned, image_header, num_words_hdr, num_words_body, exe_addr_body, im_addr_hdr)
            )

        with open(out_path, "wb") as out_f:
            for idx, (sec, payload_aligned, image_header, num_words_hdr, num_words_body, exe_addr_body, im_addr_hdr) in enumerate(packed_sections):
                # Set flags: FLAG_JUMP_ADDRESS for first section, FLAG_LAST_IMAGE for last, otherwise FLAG_WARM_BOOT
                if idx == 0:
                    msg_hdr_flags_word = srw1500_image_gen_config.FLAG_JUMP_ADDRESS
                    is_first = True
                else:
                    is_first = False
                    if idx == len(packed_sections) - 1:
                        msg_hdr_flags_word = srw1500_image_gen_config.FLAG_LAST_IMAGE
                    else:
                        msg_hdr_flags_word = srw1500_image_gen_config.FLAG_WARM_BOOT

                opcode_header = build_opcode_header_v2(
                    opcode=opcode,
                    num_words_hdr=num_words_hdr,
                    num_words_body=num_words_body,
                    exe_addr_body=exe_addr_body,
                    im_addr_hdr=im_addr_hdr,
                    img_type_word=opcode_image_type,
                    msg_hdr_flags_word=msg_hdr_flags_word,
                    entry_addr=elf_entry_addr,
                    is_first_section=is_first,
                )

                packet_len = len(opcode_header) + len(image_header) + len(payload_aligned)

                out_f.write(opcode_header)
                out_f.write(image_header)
                out_f.write(payload_aligned)

                packet_count += 1
                bytes_written += packet_len

            run_command = build_run_command(elf_entry_addr)
            out_f.write(run_command)
            bytes_written += len(run_command)

    print(
        f"Generated consolidated image: {out_path}, "
        f"packets={packet_count}, total_bytes={bytes_written}"
    )

    if packet_count == 0:
        print(
            "ERROR: No section packets were generated. "
            "Verify ELF/toolchain compatibility (objcopy/readelf)."
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
