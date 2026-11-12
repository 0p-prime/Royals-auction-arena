"""Refresh public source explicitly; existing bundled input is the reproducibility snapshot."""
from pathlib import Path
import hashlib,requests
URL='https://cricsheet.org/downloads/ipl_json.zip'
if __name__=='__main__':
    p=Path(__file__).parent/'data'/'ipl_json.zip';r=requests.get(URL,timeout=120);r.raise_for_status();p.parent.mkdir(exist_ok=True);p.write_bytes(r.content);print(URL, len(r.content), hashlib.sha256(r.content).hexdigest())
