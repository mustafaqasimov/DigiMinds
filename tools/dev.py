"""Development launcher, accepting the managed preview's Vite-compatible flags."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import uvicorn
p=argparse.ArgumentParser()
p.add_argument('--host',default='127.0.0.1')
p.add_argument('--port',type=int,default=3000)
p.add_argument('--strictPort',action='store_true')
args=p.parse_args()
uvicorn.run('backend.app:app',host=args.host,port=args.port)
