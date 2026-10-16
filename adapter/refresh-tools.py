#!/opt/homebrew/bin/python3
"""Keep route/UI metadata aligned with the external CrossOver bottle launcher."""
import json, os, pathlib, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parent
TOOLS = pathlib.Path.home()/'Library/Application Support/notproton/tools'
RECORD = ROOT/'tool-metadata-backup.json'

def transform(text, saved):
    output=[]
    for line in text.splitlines(keepends=True):
        row=line.rstrip('\r\n').split('\t')
        if len(row)!=4 or not row[0].startswith('notproton') or row[2]!='fex':
            output.append(line)
            continue
        row[2]='rosetta'
        row[3]='CrossOver - Steam bottle'
        changed='\t'.join(row)+'\n'
        saved[row[0]]={'original':line,'applied':changed}
        output.append(changed)
    return ''.join(output)

def atomic(path, text):
    fd,name=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as out: out.write(text)
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def main():
    if not TOOLS.is_file(): return
    original=TOOLS.read_text()
    saved=json.loads(RECORD.read_text()) if RECORD.exists() else {}
    if '--restore' in sys.argv:
        updated=''.join(saved.get(line.split('\t')[0],{}).get('original',line)
                        if saved.get(line.split('\t')[0],{}).get('applied')==line else line
                        for line in original.splitlines(keepends=True))
    else:
        updated=transform(original,saved)
        if updated!=original: atomic(RECORD,json.dumps(saved,indent=2))
    if updated!=original: atomic(TOOLS,updated)

if __name__=='__main__': main()
