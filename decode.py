import base64
with open('apply_changes.b64', 'rb') as f:
    data = f.read().replace(b'
', b'').replace(b'', b'')
decoded = base64.b64decode(data)
with open('apply_changes.py', 'wb') as f:
    f.write(decoded)
print('Decoded successfully!')