import urllib.request

req = urllib.request.Request(
    'http://127.0.0.1:6767/api/runs/batch-delete',
    data=b'{"run_ids": [0]}',
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    with urllib.request.urlopen(req) as response:
        print("Success:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code} - {e.reason}")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
