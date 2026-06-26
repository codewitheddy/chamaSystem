"""Run once: strips non-ASCII bytes from landing.html and re-saves as UTF-8."""
import os

path = os.path.join('templates', 'tenants', 'landing.html')

# Read as binary
with open(path, 'rb') as f:
    raw = f.read()

print(f"Original size: {len(raw)} bytes")
bad = [(i, b) for i, b in enumerate(raw) if b > 127]
print(f"Non-ASCII bytes found: {len(bad)}")
for i, b in bad[:20]:
    ctx = raw[max(0, i-40):i+40]
    print(f"  pos={i} 0x{b:02X}  ...{ctx}...")

if bad:
    # Replace each bad byte with its closest ASCII equivalent or remove it
    fixed = bytearray()
    replacements = {
        0x97: b'--',   # em dash
        0x96: b'-',    # en dash
        0x91: b"'",    # left single quote
        0x92: b"'",    # right single quote
        0x93: b'"',    # left double quote
        0x94: b'"',    # right double quote
        0x85: b'...',  # ellipsis
        0xa0: b' ',    # non-breaking space
    }
    for b in raw:
        if b <= 127:
            fixed.append(b)
        elif b in replacements:
            fixed.extend(replacements[b])
        # else skip unknown non-ASCII bytes

    with open(path, 'wb') as f:
        f.write(bytes(fixed))
    print(f"Fixed. New size: {len(fixed)} bytes")
else:
    print("File is already clean ASCII/UTF-8.")
