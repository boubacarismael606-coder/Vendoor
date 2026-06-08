import urllib.request
import zipfile
import io
import os

url = 'https://bin.ngrok.com/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip'
path = os.path.expanduser(r'~\\AppData\\Local\\ngrok')
print('target', path)
os.makedirs(path, exist_ok=True)
with urllib.request.urlopen(url, timeout=120) as r:
    data = r.read()
print('downloaded', len(data), 'bytes')
with zipfile.ZipFile(io.BytesIO(data)) as zf:
    names = zf.namelist()
    print('names', names)
    for name in names:
        if name.endswith('ngrok.exe'):
            outpath = os.path.join(path, 'ngrok.exe')
            with open(outpath, 'wb') as f:
                f.write(zf.read(name))
            print('wrote', outpath)
