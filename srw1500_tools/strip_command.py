import sys
import os

sys.stdout = open(os.devnull, 'w')
# sys.stdout = sys.__stdout__

if len(sys.argv) != 3:
    print(f"Usage: {sys.argv[0]} <input.bin> <output.bin>")
    sys.exit(1)

INPUT_BIN = sys.argv[1]
OUTPUT_BIN = sys.argv[2]
STRIP_LEN = 32

if not os.path.exists(INPUT_BIN):
    raise FileNotFoundError(f"Input file not found: {INPUT_BIN}")

with open(INPUT_BIN, "rb") as f:
    data = f.read()

if len(data) <= STRIP_LEN:
    raise RuntimeError("Binary too small to strip header")

# Strip first 32 bytes
data = data[STRIP_LEN:]

with open(OUTPUT_BIN, "wb") as f:
    f.write(data)

print(f"Stripped {STRIP_LEN} bytes:")
print(f"  Input : {INPUT_BIN}")
print(f"  Output: {OUTPUT_BIN}")
