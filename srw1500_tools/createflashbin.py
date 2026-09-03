import sys
import os

sys.stdout = open(os.devnull, 'w')
# sys.stdout = sys.__stdout__

def create_image(output_file, size, fill=0xFF):
    """Create a base image of given size filled with the given byte."""
    out_dir = os.path.dirname(output_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(output_file, "wb") as f:
        f.write(bytes([fill]) * size)

def read_input_payload(input_file):
    """Read payload for insertion, with fallback for stripped app image."""
    if os.path.exists(input_file):
        with open(input_file, "rb") as in_f:
            return in_f.read()

    # Backward-compatible fallback used by flash build when stripped image
    # was not materialized but the source signed image is available.
    fallback_file = input_file.replace("_flash_", "_", 1)
    if fallback_file != input_file and os.path.exists(fallback_file):
        with open(fallback_file, "rb") as in_f:
            data = in_f.read()
        if len(data) <= 32:
            raise RuntimeError(f"Fallback input too small to strip header: {fallback_file}")
        return data[32:]

    raise FileNotFoundError(f"Input file not found: {input_file}")

def insert_file(output_file, input_file, offset):
    """Insert input_file into output_file at the given offset."""
    payload = read_input_payload(input_file)
    with open(output_file, "r+b") as out_f:
        out_f.seek(offset)
        out_f.write(payload)

def main():
    if len(sys.argv) < 4 or (len(sys.argv) - 2) % 2 != 0:
        print(f"Usage: {sys.argv[0]} output_file input1 offset1 [input2 offset2 ...]")
        print("Example: python script.py image.bin file1.bin 0x1000 file2.bin 0x20000")
        sys.exit(1)

    output_file = sys.argv[1]
    IMAGE_SIZE = 1 * 1024 * 1024  # 8 MB

    # Step 1: create base file
    create_image(output_file, IMAGE_SIZE)

    # Step 2: insert files
    for i in range(2, len(sys.argv), 2):
        input_file = sys.argv[i]
        offset = int(sys.argv[i + 1], 0)  # supports decimal or hex (0x...)
        print(f"Inserting {input_file} at offset {hex(offset)}")
        insert_file(output_file, input_file, offset)

if __name__ == "__main__":
    main()
