import urllib.request
import zipfile
import io
import os

url = 'https://bin.ngrok.com/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip'
path = os.path.expanduser(r'~\\AppData\\Local\\ngrok')
print('target', path)
os.makedirs(path, exist_ok=True)
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0'
})
with urllib.request.urlopen(req, timeout=120) as r:
    total = 0
    buf = io.BytesIO()
    while True:
        chunk = r.read(8192)
        if not chunk:
            break
        buf.write(chunk)
        total += len(chunk)
    print('downloaded', total, 'bytes')
    data = buf.getvalue()
print('len data', len(data))
with zipfile.ZipFile(io.BytesIO(data)) as zf:
    names = zf.namelist()
    print('names', names)
    for name in names:
        if name.endswith('ngrok.exe'):
            outpath = os.path.join(path, 'ngrok.exe')
            with open(outpath, 'wb') as f:
                f.write(zf.read(name))
            print('wrote', outpath)
