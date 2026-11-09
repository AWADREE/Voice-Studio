"""Sample-first workflows use one in-memory voice, with explicit .pt persistence."""
from dataclasses import replace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import torch
import app
from test_fixture import TEST_VOICE

class SampleFirstTests(unittest.TestCase):
    def test_clone_audition_and_explicit_original_prompt_roundtrip(self):
        item=app.read_voice(TEST_VOICE)
        fake=MagicMock()
        fake.generate_voice_clone.return_value=([np.zeros(2400,dtype=np.float32)],24000)
        for identity_only in (False,True):
            item=replace(item,x_vector_only_mode=identity_only,icl_mode=not identity_only,ref_text=None if identity_only else 'Original words')
            fake.create_voice_clone_prompt.return_value=[item]
            with self.subTest(identity_only=identity_only),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);voices=root/'voices';outputs=root/'outputs'
                with patch.object(app,'VOICES',voices),patch.object(app,'OUTPUTS',outputs),patch.object(app,'load_model',return_value=fake),patch.object(app,'release_model'),patch.object(app,'save_voice') as encode_save:
                    result=app.clone_audition('ref.wav','Original words',not identity_only,'Different audition words','Calm','English',4,True,*app.SETTING_DEFAULTS)
                    self.assertFalse(voices.exists())
                    state=result[3]
                    self.assertEqual(state['source'],'clone_reference')
                    self.assertEqual(state['sample_text'],'Different audition words')
                    self.assertEqual(state['transcript'],'' if identity_only else 'Original words')
                    self.assertIs(fake.generate_voice_clone.call_args.kwargs['voice_clone_prompt'][0],item)
                    self.assertFalse(voices.exists())
                    # Save must not encode the audition WAV or re-load either model.
                    with patch.object(app,'load_model') as load:
                        filename,status=app.save_preview_voice(state,False)
                        load.assert_not_called()
                    encode_save.assert_not_called()
                    payload=torch.load(filename,weights_only=True,map_location='cpu')['items'][0]
                    self.assertTrue(torch.equal(payload['ref_spk_embedding'],item.ref_spk_embedding))
                    self.assertEqual(payload['ref_text'],None if identity_only else 'Original words')
                    self.assertIn('original reference audio',status)
                    self.assertEqual(len(list(voices.glob('*.pt'))),1)

    def test_design_is_single_sample_and_only_explicit_save_encodes_it(self):
        fake=MagicMock();fake.generate_voice_design.return_value=([np.zeros(2400,dtype=np.float32)],24000)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.object(app,'OUTPUTS',root/'outputs'),patch.object(app,'VOICES',root/'voices'),patch.object(app,'load_model',return_value=fake),patch.object(app,'release_model'),patch.object(app,'save_voice',return_value=('chosen.pt','ok')) as save:
                result=app.generate_design_preview('Exact sample words','Warm voice','English',4,True,*app.SETTING_DEFAULTS)
                state=result[3]
                save.assert_not_called();self.assertFalse((root/'voices').exists())
                self.assertEqual(state['source'],'design_sample')
                self.assertEqual(state['transcript'],'Exact sample words')
                save.assert_not_called()
                filename,_=app.save_preview_voice(state,False)
                self.assertEqual(filename,'chosen.pt')
                save.assert_called_once_with(str(Path(result[0]).resolve()),'Exact sample words',False)

    def test_generate_preserves_both_single_and_timestamped_dispatch(self):
        rows=[{'minutes':0,'seconds':2,'text':'First'},{'minutes':1,'seconds':0,'text':'Second'}]
        for mode in ('single','batch'):
            with patch.object(app,'generate_commentary_mode',return_value=tuple(range(15))) as generate,patch.object(app,'clone_audition') as clone,patch.object(app,'generate_design_preview') as design:
                result=app.generate_workflow_mode('generate',mode,rows,0,None,'',True,'', 'selected.pt','Single sample','Calm','English',4,True,False,*app.SETTING_DEFAULTS)
            self.assertEqual(result[:15],tuple(range(15)))
            self.assertEqual(generate.call_args.args[:4],(mode,rows,'selected.pt','Single sample'))
            clone.assert_not_called();design.assert_not_called()

    def test_corrected_design_transcript_saves_without_approval(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);wav=root/'sample.wav';wav.write_bytes(b'fixture')
            state={'audio':str(wav),'sha256':hashlib.sha256(wav.read_bytes()).hexdigest(),'transcript':'Captured words','source':'design_sample'}
            with patch.object(app,'OUTPUTS',root),patch.object(app,'save_voice',return_value=('design.pt','saved')) as save:
                file,status=app.save_preview_corrected(state,False,' Corrected words ',True)
            self.assertEqual(file['value'],'design.pt')
            save.assert_called_once_with(str(wav.resolve()),'Corrected words',False)
            self.assertEqual(state['transcript'],'Captured words')

    def test_corrected_clone_transcript_retains_original_prompt_without_approval(self):
        import hashlib
        from dataclasses import asdict
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);wav=root/'sample.wav';wav.write_bytes(b'fixture')
            item=app.read_voice(TEST_VOICE)
            state={'audio':str(wav),'sha256':hashlib.sha256(wav.read_bytes()).hexdigest(),'transcript':'Captured words','source':'clone_reference','prompt':asdict(item),'identity_only':False}
            with patch.object(app,'OUTPUTS',root),patch.object(app,'VOICES',root/'voices'),patch.object(app,'load_model') as load,patch.object(app,'save_voice') as encode:
                file,status=app.save_preview_corrected(state,False,' Corrected reference words ',True)
                saved=app.read_voice(file['value'])
            load.assert_not_called();encode.assert_not_called()
            self.assertEqual(saved.ref_text,'Corrected reference words')
            self.assertTrue(torch.equal(saved.ref_spk_embedding,item.ref_spk_embedding))
            self.assertTrue(torch.equal(saved.ref_code,item.ref_code))
            self.assertEqual(state['transcript'],'Captured words')

    def test_ui_has_no_audition_approval_checkbox(self):
        ui=app.build_ui();cfg=ui.get_config_file();components={c['id']:c for c in cfg['components']}
        labels=[c['props'].get('label','').lower() for c in cfg['components'] if c['type']=='checkbox']
        self.assertFalse(any('approve' in label or 'listened' in label or 'confirm' in label for label in labels))
        save=next(d for d in cfg['dependencies'] if d.get('api_name')=='save_preview_voice')
        self.assertEqual(components[save['inputs'][1]]['type'],'state')
        self.assertFalse(ui.blocks[save['inputs'][1]].value)

if __name__=='__main__':unittest.main()
