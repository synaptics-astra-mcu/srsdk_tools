import subprocess
import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Shared config lives alongside this script, directly under srw1500_tools/, so
# both the RAM and flash generators use a single srw1500_image_gen_config.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import srw1500_image_gen_config

application = ""
jedec = "JEDEC64"
partition = "-p:0x600-0x800"

# sys.stdout = open(os.devnull, 'w')
sys.stdout = sys.__stdout__

def detect_os():
    if os.name == 'nt':
        return "Windows"
    elif os.name == 'posix':
        return "Unix"
    else:
        return "Unknown OS"
    
def sha512_checksum(file_path):
    """Calculate SHA-512 checksum of a file using OpenSSL."""
    try:
        result = subprocess.run(['openssl', 'dgst', '-sha512', file_path], capture_output=True, text=True, check=True)
        checksum = result.stdout.strip().split()[-1]
        return checksum
    except subprocess.CalledProcessError as e:
        print(f"Error calculating checksum: {e}")
        return None

def sha256_checksum(file_path):
    """Calculate SHA-256 checksum of a file using OpenSSL."""
    try:
        result = subprocess.run(['openssl', 'dgst', '-sha256', file_path], capture_output=True, text=True, check=True)
        checksum = result.stdout.strip().split()[-1]
        return checksum
    except subprocess.CalledProcessError as e:
        print(f"Error calculating checksum: {e}")
        return None
    

    
def sign_with_private_key(private_key, data_file):
    """
    Sign the contents of a file using a private key with OpenSSL.

    :param private_key: Path to the private key (PEM)
    :param data_file: Path to the input file containing data (e.g. hash.bin)
    :return: Signature as bytes, or None on error
    """
    try:
        result = subprocess.run(
            ['openssl', 'pkeyutl', '-sign', '-inkey', private_key, '-in', data_file],
            capture_output=True,  # capture stdout (signature)
            check=True            # raise CalledProcessError on failure
        )
        signature = result.stdout  # raw binary signature
        return signature
    except subprocess.CalledProcessError as e:
        print(f"[!] Error signing data: {e}\n{e.stderr.decode(errors='ignore')}")
        return None

def generate_ecc_keypair(curve_name='prime256v1'):
    """Generate ECC private and public key using OpenSSL."""
    try:
        # Generate the private key
        private_key_result = subprocess.run(
            ['openssl', 'ecparam', '-name', curve_name, '-genkey', '-noout'],
            capture_output=True, text=True, check=True
        )
        private_key = private_key_result.stdout.strip()

        # Generate the public key from the private key
        public_key_result = subprocess.run(
            ['openssl', 'ec', '-in', '/dev/stdin', '-pubout'],
            input=private_key, capture_output=True, text=True, check=True
        )
        public_key = public_key_result.stdout.strip()

        return private_key, public_key
    except subprocess.CalledProcessError as e:
        print(f"Error generating ECC keypair: {e}")
        return None, None

import subprocess
import tempfile
import os

def extract_r_s_from_signature(der_signature_bytes):
    """
    Parses a DER-encoded ECDSA signature using OpenSSL to extract R and S values.

    Args:
        der_signature_bytes (bytes): Binary content of DER-encoded signature (e.g., SPK_Signature.bin)

    Returns:
        tuple: (R, S) as hexadecimal strings
    """
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.write(der_signature_bytes)
        tmp_file_path = tmp_file.name

    try:
        # Run OpenSSL asn1parse to parse the DER file
        result = subprocess.run(
            ['openssl', 'asn1parse', '-in', tmp_file_path, '-inform', 'DER'],
            capture_output=True, text=True, check=True
        )

        lines = result.stdout.strip().splitlines()
        hex_data = []

        for line in lines:
            if "INTEGER" in line:
                # Example:  0:d=0  hl=2 l=  32 prim: INTEGER           :E1E6...
                colon_index = line.rfind(':')
                if colon_index != -1:
                    hex_val = line[colon_index + 1:].strip()
                    hex_data.append(hex_val)

        if len(hex_data) < 2:
            raise ValueError("Failed to extract R and S")

        r, s = hex_data[0], hex_data[1]
        return r, s

    finally:
        os.remove(tmp_file_path)



def read_file_to_array(input_file_name):
    file_bin_data = None
    # Opening the binary file in binary mode as rb(read binary)
    try:
        with open(input_file_name, mode="rb") as f:
            file_bin_data = f.read()
        f.close()    
    except Exception as error:
        # handle the exception
        # print('An exception occurred during read file to array', an_exception=str(error)) 
        return
                
    return file_bin_data

def int_to_4byte_array(length: int, byteorder: str = "little"):
    return list(length.to_bytes(4, byteorder=byteorder))

def parse_u32_arg(value: str) -> list[int]:
    return int_to_4byte_array(int(value, 0), byteorder="little")

def pad_with_zeroes(data: bytes, max_size: int) -> bytes:
    """
    Pads the given data with 0x00 bytes until it reaches max_size.
    If data is already larger than max_size, raises an error.
    Returns a new bytes object of length max_size.
    """
    if len(data) > max_size:
        raise ValueError(f"Data size {len(data)} is greater than max_size {max_size}")

    padding_needed = max_size - len(data)
    return data + b'\x00' * padding_needed 

def cmd_output(cmd):
    """
    Executes a command and returns its output as a string.

    Args:
        cmd (str): The command to execute.

    Returns:
        str: The output of the command as a string.
    """
    output = subprocess.check_output(cmd)
    return output.decode() 

def get_entry_point_address(elf_file_name):
    """
    Returns the entry point address of an ELF file.

    Args:
        elf_file_name (str): The name of the ELF file.

    Returns:
        int: The entry point address of the ELF file.
    """
    hex_address = ''
    cmd = [
        "readelf",
        "-h",
        elf_file_name,
    ]
    output = cmd_output(cmd)
    output_list = output.split("\n")
    for var in output_list:
        if srw1500_image_gen_config.ENTRY_POINT_ADDRESS in var:
            requested_line = var.split()
            for param in requested_line:
                if "0x" in param:
                    hex_address = int(param[2:], 16)
    return hex_address  

def resolve_signing_key_paths(args):
    if args.private_key:
        file_spk_privkey = os.path.abspath(args.private_key)
    else:
        file_spk_privkey = os.path.join(os.path.dirname(__file__), srw1500_image_gen_config.SPK_PRIVKEY)

    if args.public_key:
        file_spk_pubkey = os.path.abspath(args.public_key)
    else:
        file_spk_pubkey = os.path.join(os.path.dirname(__file__), srw1500_image_gen_config.SPK_PUBKEY)

    has_signing_keys = os.path.isfile(file_spk_privkey) and os.path.isfile(file_spk_pubkey)
    return file_spk_privkey, file_spk_pubkey, has_signing_keys

def main(args):

    header_array = bytearray()
    sign_img_sha256_array = bytearray()
    bin_data_length = 0
    total_length = 0
    
    if args.file_name:
        print("File name:"+ args.file_name)
    else:
        print("File name not present")
        exit(-1)

    # Create output file. Keep the historical default next to this script, but
    # allow build systems to place generated files in their own output tree.
    if args.output_file:
        srw1500_image_gen_config.output_file_name_spk_host = os.path.abspath(args.output_file)
    else:
        srw1500_image_gen_config.output_file_name_spk_host = os.path.join(os.path.dirname(__file__), "srw1500_signed.bin")
    srw1500_image_gen_config.check_path(srw1500_image_gen_config.output_file_name_spk_host)

    # Create files for SPK break down. Sysbuild can run multiple images, so let
    # callers keep these temporary files out of the shared tool directory.
    artifact_dir = os.path.abspath(args.artifact_dir) if args.artifact_dir else os.path.dirname(__file__)
    os.makedirs(artifact_dir, exist_ok=True)

    file_spk_privkey, file_spk_pubkey, has_signing_keys = resolve_signing_key_paths(args)
    print("Private key file name:"+ file_spk_privkey)
    print("Public key file name:"+ file_spk_pubkey)
    file_spk_hash           =  os.path.join(artifact_dir,  srw1500_image_gen_config.SPK_HASH)
    srw1500_image_gen_config.check_path(file_spk_hash)
    print("Hash file name:"+ file_spk_hash)
    file_spk_sha256_in      =  os.path.join(artifact_dir,  srw1500_image_gen_config.SPK_SHA256_in)
    srw1500_image_gen_config.check_path(file_spk_sha256_in)
    file_spk_sha256_out     =  os.path.join(artifact_dir,  srw1500_image_gen_config.SPK_SHA256_out)
    srw1500_image_gen_config.check_path(file_spk_sha256_out)
    print("Hash file name:"+ file_spk_hash)
    file_spk_signature      =  os.path.join(artifact_dir,  srw1500_image_gen_config.SPK_SIGNATURE)
    srw1500_image_gen_config.check_path(file_spk_signature)
    print("Signature file name:"+ file_spk_signature)

    print("\n\n")
    
    load_address = parse_u32_arg(args.load_address) if args.load_address else None
    entry_point = parse_u32_arg(args.entry_point) if args.entry_point else None
    if args.use_elf_entry:
        if not args.app_elf:
            raise ValueError("--use-elf-entry requires --app_elf")
        entry_point = int_to_4byte_array(get_entry_point_address(args.app_elf), byteorder="little")

    # Read the input file and store it in a byte array
    bin_data_for_output = read_file_to_array(args.file_name) 
    file_size_dec = (int)(os.path.getsize(args.file_name))
    print("File size in bytes:", file_size_dec)
    total_length = total_length + file_size_dec
    total_length = total_length + srw1500_image_gen_config.HEADER_SIZE  # Add header size

    #store length of binary data
    file_size = int_to_4byte_array(total_length, byteorder="little")
    print("File size in bytes:", total_length)


    #Add header
    if (args.image_type == "APBL"):
        # OPCODE
        header2add_list = list(srw1500_image_gen_config.SYNC_1) + list(srw1500_image_gen_config.SYNC_2) + list(srw1500_image_gen_config.SRV_ID) + list(srw1500_image_gen_config.OPCODE_DWNLD_APBL_IMG)
    else:
        # OPCODE
        header2add_list = list(srw1500_image_gen_config.SYNC_1) + list(srw1500_image_gen_config.SYNC_2) + list(srw1500_image_gen_config.SRV_ID) + list(srw1500_image_gen_config.OPCODE_DWNLD_APP_IMG)

    header_array.extend(header2add_list)
    # image length in bytes  
    header_array.extend(list(file_size))  
    #pad zeroes
    header_array.extend(list(srw1500_image_gen_config.zero_pad_24_bytes))  

    if (args.image_type == "APBL"):
        # image type, image version
        header2add_list =  list(srw1500_image_gen_config.IMG_TYPE_APBL_8_11) + list(srw1500_image_gen_config.IMG_VER_APBL_12_15)
    else:
        # image type, image version
        header2add_list =  list(srw1500_image_gen_config.IMG_TYPE_APP_8_11) + list(srw1500_image_gen_config.IMG_VER_APP_12_15)
    
    header_array.extend(header2add_list)
    sign_img_sha256_array.extend(header2add_list)
    # image length in bytes 
    header_array.extend(list(file_size))
    sign_img_sha256_array.extend(list(file_size))
    # cipher
    header_array.extend(list(srw1500_image_gen_config.CIPHER_20_35))
    sign_img_sha256_array.extend(list(srw1500_image_gen_config.CIPHER_20_35))

    #Generate SHA-512 for spk img
    sha512_out = sha512_checksum(args.file_name)
    if sha512_out is not None:
        sha512_out_bin = bytes.fromhex(sha512_out)

    #Length of SHA512 file
    if sha512_out is not None:
        bin_data_length = len(sha512_out)
        print(f"Length of binary data for SHA-512: {bin_data_length}")
    else:
        print("No binary data available for length calculation.")
    
    #checksum
    header_array.extend(sha512_out_bin) 
    sign_img_sha256_array.extend(sha512_out_bin)

    #write the data to output file
    with open(file_spk_hash, 'wb+') as file:
        file.write(sha512_out_bin)     
    
    print("sha512_out Key:", sha512_out)
    
    # segment ID, version, RFU
    if (args.image_type == "APBL"):
        destination_bytes = load_address or list(srw1500_image_gen_config.DESTINATION_ADDRESS_APBL)
        entry_bytes = entry_point or list(srw1500_image_gen_config.BOOTLOADER_ENTRY_POINT)
        header2add_list = list(srw1500_image_gen_config.SEG_ID_64_67) + list(srw1500_image_gen_config.VER_68_71) + list(srw1500_image_gen_config.PRODUCTION_FLAG) + list(srw1500_image_gen_config.RFU_72_75) + destination_bytes + entry_bytes
    else:
        if entry_point:
            entry_bytes = entry_point
        else:
            entry = get_entry_point_address(args.app_elf)
            entry_bytes = list(entry.to_bytes(4, byteorder="little"))
        if (args.destination == "FLASH"):
            destination_bytes = load_address or list(srw1500_image_gen_config.DESTINATION_ADDRESS_XSPI_APP)
            header2add_list = list(srw1500_image_gen_config.SEG_ID_64_67) + list(srw1500_image_gen_config.VER_68_71) + list(srw1500_image_gen_config.PRODUCTION_FLAG) + list(srw1500_image_gen_config.RFU_72_75) + destination_bytes + entry_bytes
        else:
            destination_bytes = load_address or list(srw1500_image_gen_config.DESTINATION_ADDRESS_APP)
            header2add_list = list(srw1500_image_gen_config.SEG_ID_64_67) + list(srw1500_image_gen_config.VER_68_71) + list(srw1500_image_gen_config.PRODUCTION_FLAG) + list(srw1500_image_gen_config.RFU_72_75) + destination_bytes + entry_bytes
    header_array.extend(header2add_list)
    sign_img_sha256_array.extend(header2add_list)

    with open(file_spk_sha256_in, 'wb+') as file:
        file.write(sign_img_sha256_array)

    #generate SHA-256 checksum
    sha256_out = sha256_checksum(file_spk_sha256_in)
    if sha256_out is not None:
        sha256_out_bin = bytes.fromhex(sha256_out)

    #Length of SHA256 file
    if sha256_out is not None:
        bin_data_length = len(sha256_out)
        print(f"Length of binary data for SHA-256: {bin_data_length}")
    else:
        print("No binary data available for length calculation.")
    
    with open(file_spk_sha256_out, 'wb+') as file:
        file.write(sha256_out_bin)

    print("sha256_out Key:", sha256_out)

    signature = b'\x00' * 512
    if has_signing_keys:
        print("Private key file path:", file_spk_privkey)
        print("Public key file path:", file_spk_pubkey)

        signature_der = sign_with_private_key(file_spk_privkey, file_spk_sha256_out)

        if signature_der:
            print("Signature:", signature_der)
            bin_data_length = len(signature_der)
            print(f"Length signature of binary data for image generation: {bin_data_length}")

            with open(file_spk_signature, 'wb+') as file:
                file.write(signature_der)

            r, s = extract_r_s_from_signature(signature_der)

            if r and s:
                print(f"Extracted r: {r},\n s: {s}")
                signature = pad_with_zeroes(bytes.fromhex(r + s), 512)
            else:
                print("Failed to extract r and s values from signature.")
        else:
            print("Failed to generate signature.")
    else:
        print("Private/public key not found, skipping signing.")

    header_array.extend(signature)  # signature

    header_array.extend(bin_data_for_output)  # img body


    #write the data to utput file
    with open(srw1500_image_gen_config.output_file_name_spk_host, 'wb+') as file:                
        file.write(header_array)       

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="DAX_Filesyatem")

    parser.add_argument('-f', '--file_name', type=str, help='create file', default = "")
    parser.add_argument('-private', '--private_key', type=str, help='private key', default = "")
    parser.add_argument('-public', '--public_key', type=str, help='public key', default = "")
    parser.add_argument('-i', '--image_type', type=str, help='image type', default = "")
    parser.add_argument('-a', '--app_elf', type=str, help='app input file', default = "")
    parser.add_argument('-d', '--destination', type=str, help='destination type', default = "")
    parser.add_argument('-o', '--output_file', type=str, help='output file', default = "")
    parser.add_argument('--artifact-dir', type=str, help='temporary artifact directory', default = "")
    parser.add_argument('--load-address', type=str, help='payload load address override', default = "")
    parser.add_argument('--entry-point', type=str, help='payload entry point override', default = "")
    parser.add_argument('--use-elf-entry', action='store_true', help='use --app_elf entry point')
    # parser.add_argument('-d', help='list file', action='store_true')
    # parser.add_argument('-a', action='extend', nargs="+", help='add files')
    # parser.add_argument('-x', action='extend', nargs="+", help='extract file from flash bin')

    args = parser.parse_args()

    print("Running on:", detect_os())

    if (detect_os() == "Windows"):
        application = "daxQSPI.exe"
    else:
        application = "openssl"

    print("Application:", application)

    main(args)