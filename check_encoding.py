import sys
path = 'templates/tenants/landing.html'
with open(path, 'rb') as f:
    data = f.read()
print(f"File size: {len(data)} bytes")
bad = [(i, b) for i, b in enumerate(data) if b > 127]
print(f"Non-ASCII bytes: {len(bad)}")
for i, b in bad[:10]:
    ctx = data[max(0,i-30):i+30]
    print(f"  pos={i} byte=0x{b:02X} context={ctx}")
