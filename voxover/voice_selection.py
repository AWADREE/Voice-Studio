"""Session-scoped latest-selection ordering, independent of model inference."""
import threading
class VoiceSelection:
 def __init__(self):self.lock=threading.RLock();self.sessions={}
 def begin(self,session):
  with self.lock:
   s=self.sessions.setdefault(session,{'revision':0,'path':None});s['revision']+=1;return s['revision']
 def select(self,session,path):
  with self.lock:
   n=self.begin(session);self.sessions[session]['path']=path;return n
 def commit(self,session,token,path):
  with self.lock:
   s=self.sessions.get(session)
   if not s or s['revision']!=token:return False
   s['path']=path;return True
SELECTION=VoiceSelection()
