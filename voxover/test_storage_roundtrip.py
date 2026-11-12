from test_fixture import TEST_VOICE
from pathlib import Path
from unittest.mock import patch
import app,numpy as np
from storage_locations import StorageLocations
s=StorageLocations(app.ROOT/'Temp'/'storage-picker-qa')
app.OUTPUTS=s.values['output'];app.VOICES=s.values['voice']
item=app.read_voice(str(TEST_VOICE))
class Fake:
 def generate_voice_clone(self,**kwargs):return [np.zeros(2400,dtype=np.float32)],24000
 def create_voice_clone_prompt(self,**kwargs):return [item]
with patch.object(app,'load_model',return_value=Fake()):
 wav,_,_=app.generate(str(TEST_VOICE),'Storage test.','','English',-1,False,False)
 pt,_=app.save_voice(wav,'Storage test.',False,release_after=False)
assert Path(wav).parent==s.values['output'] and Path(wav).is_file()
assert Path(pt).parent==s.values['voice'] and Path(pt).is_file()
print('Verified persisted locations, actual WAV/JSON/PT writes with mocked inference:',wav,pt)
