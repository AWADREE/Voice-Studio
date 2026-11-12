"""Local-only persisted output locations. Never moves existing user files."""
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse

class StorageLocations:
    def __init__(self, root):
        self.root=Path(root)
        self.config=self.root/'storage-locations.json'
        self.values={'output':self.root/'Outputs','voice':self.root/'Voices'}
        self.output_history={self.values['output'].resolve()}
        if self.config.exists():
            data=json.loads(self.config.read_text(encoding='utf-8'))
            for key in self.values:
                if key in data:self.values[key]=self.validate(data[key])
            self.output_history.add(self.values['output'].resolve())
    @staticmethod
    def validate(value):
        p=Path(value).expanduser()
        if not p.is_absolute() or str(p).startswith(('\\\\','//')):
            raise ValueError('Choose an absolute folder on a local drive, not a network share.')
        p=p.resolve()
        if str(p).startswith(('\\\\','//')):raise ValueError('Network locations are not supported.')
        if p.exists() and not p.is_dir():raise ValueError('Choose a folder, not a file.')
        return p
    def set(self,key,value):
        if key not in self.values:raise ValueError('Unknown storage location.')
        if not value:return False
        p=self.validate(value)
        p.mkdir(parents=True,exist_ok=True)
        # Exclusive disposable probe verifies real write access without changing existing files.
        import tempfile
        with tempfile.TemporaryFile(dir=p):pass
        updated=dict(self.values);updated[key]=p
        tmp=self.config.with_suffix('.tmp')
        tmp.write_text(json.dumps({k:str(v) for k,v in updated.items()},indent=2),encoding='utf-8')
        os.replace(tmp,self.config)
        self.values=updated
        if key=='output':self.output_history.add(p.resolve())
        return True

def require_local_ui(request):
    if request is None or getattr(getattr(request,'client',None),'host',None) not in ('127.0.0.1','::1','localhost'):
        raise ValueError('Folder selection is only available from the local Voxover browser.')
    headers=request.headers
    origin=headers.get('origin') or headers.get('referer')
    parsed=urlparse(origin or '')
    if parsed.scheme not in ('http','https') or parsed.hostname not in ('127.0.0.1','localhost','::1'):
        raise ValueError('Open Voxover locally before choosing a folder.')
    # Origin must match the server port, not another local web app.
    host=urlparse('http://'+headers.get('host',''))
    if parsed.port!=host.port:raise ValueError('Folder selection requires the same local Voxover origin.')

def choose_folder(initial,title):
    # A separate STA Windows Forms dialog avoids Tk/Shell deadlocks in web worker threads.
    script="""Add-Type -AssemblyName System.Windows.Forms
$dialog=New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description=$env:VOXOVER_PICKER_TITLE
$dialog.SelectedPath=$env:VOXOVER_PICKER_INITIAL
$dialog.ShowNewFolderButton=$true
$owner=New-Object System.Windows.Forms.Form
$owner.Text='Voxover folder selection'
$owner.TopMost=$true
$owner.ShowInTaskbar=$false
$owner.Size=New-Object Drawing.Size(1,1)
$owner.Opacity=0
$owner.Show()
$owner.Activate()
try { if($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK){[Console]::OutputEncoding=[Text.Encoding]::UTF8;[Console]::Write($dialog.SelectedPath)} } finally {$dialog.Dispose();$owner.Close();$owner.Dispose()}
"""
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=1
    result=subprocess.run(['powershell.exe','-NoProfile','-STA','-Command',script],startupinfo=startup,capture_output=True,text=True,encoding='utf-8-sig',env={**os.environ,'VOXOVER_PICKER_TITLE':title,'VOXOVER_PICKER_INITIAL':str(initial)},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=True,timeout=300)
    return result.stdout.strip()
