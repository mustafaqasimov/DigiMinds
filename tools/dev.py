"""Development launcher, accepting the managed preview's Vite-compatible flags."""
import argparse
import sys
import os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
# npm/preview entry points should use the same optional YOLO packages as BASLAT.
root=Path(__file__).resolve().parent.parent
environment=root/'.venv'
python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if python.is_file() and Path(sys.prefix).resolve()!=environment.resolve():
    os.execv(str(python),[str(python),str(Path(__file__).resolve()),*sys.argv[1:]])
import uvicorn
p=argparse.ArgumentParser()
p.add_argument('--host',default='127.0.0.1')
p.add_argument('--port',type=int,default=3000)
p.add_argument('--strictPort',action='store_true')
p.add_argument('--ssl-certfile')
p.add_argument('--ssl-keyfile')
args=p.parse_args()
uvicorn.run('backend.app:app',host=args.host,port=args.port,ssl_certfile=args.ssl_certfile,ssl_keyfile=args.ssl_keyfile)
