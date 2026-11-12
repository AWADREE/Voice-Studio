from test_fixture import TEST_VOICE
import unittest
from unittest.mock import patch
import hashlib
from pathlib import Path
import app

class WiringTests(unittest.TestCase):
    def test_voice_load_does_not_modify_source(self):
        p=Path(str(TEST_VOICE))
        before=hashlib.sha256(p.read_bytes()).hexdigest()
        item=app.read_voice(p)
        self.assertEqual(tuple(item.ref_spk_embedding.shape),(2048,))
        self.assertTrue(item.icl_mode)
        self.assertEqual(before,hashlib.sha256(p.read_bytes()).hexdigest())
    def test_instruction_is_tokenized_not_passed_as_raw_string(self):
        class Fake:
            def _build_instruct_text(self, text): return 'WRAPPED:'+text
            def _tokenize_texts(self, texts): return ['TOKENS',texts]
        self.assertEqual(app.instruction_kwargs(Fake(),' calm '),{'instruct_ids':['TOKENS',['WRAPPED:calm']]})
        self.assertEqual(app.instruction_kwargs(Fake(),' '),{})
    def test_missing_file_and_blank_text(self):
        with self.assertRaises(ValueError): app.read_voice(None)
        with patch.object(app,'load_model') as load:
            with self.assertRaises(Exception): app.generate(None,' ','','English',42,False,False)
            load.assert_not_called()
    def test_memory_guard_without_loading(self):
        with patch.object(app.torch.cuda,'is_available',return_value=True), patch.object(app.torch.cuda,'mem_get_info',return_value=(1024**3,12*1024**3)), patch.object(app.Qwen3TTSModel,'from_pretrained') as load:
            with self.assertRaisesRegex(RuntimeError,'Close the other Qwen'): app.load_model()
            load.assert_not_called()
    def test_english_ui_no_vendor_labels(self):
        ui=app.build_ui()
        cfg=ui.get_config_file()
        import json,re
        self.assertFalse(re.search('[\u3400-\u9fff]',json.dumps(cfg,ensure_ascii=False,default=str)))
        self.assertIn('Delivery instruction',str(cfg))
        self.assertIsNone(app._model)

class WorkflowTests(unittest.TestCase):
    def test_all_workflows_exist(self):
        cfg=app.build_ui().get_config_file()
        labels=[c.get('props',{}).get('label') for c in cfg['components']]
        self.assertIn('Clone & Generate',labels)
        self.assertIn('Save / Load Voice',labels)
        self.assertEqual(labels.count('Reference audio'),2)
        self.assertEqual(labels.count('Reference transcript'),2)
        apis=[d.get('api_name') for d in cfg['dependencies']]
        for name in ['clone_generate','save_voice','generate','inspect_voice']:
            self.assertIn(name,apis)
    def test_reference_validation_no_load(self):
        with patch.object(app,'load_model') as load:
            with self.assertRaises(Exception): app.save_voice(None,'',False)
            with self.assertRaises(Exception): app.save_voice('fake.wav','',False)
            load.assert_not_called()
    def test_save_round_trip(self):
        import tempfile
        from types import SimpleNamespace
        item=app.read_voice(Path(str(TEST_VOICE)))
        fake=SimpleNamespace(create_voice_clone_prompt=lambda **kw:[item])
        with tempfile.TemporaryDirectory() as tmp, patch.object(app,'ROOT',Path(tmp)), patch.object(app,'load_model',return_value=fake), patch.object(app,'release_model'):
            path,status=app.save_voice('reference.wav','Matching transcript',False)
            self.assertTrue(Path(path).exists())
            self.assertEqual(app.read_voice(path).ref_spk_embedding.shape,item.ref_spk_embedding.shape)
    def test_direct_clone_routes_instructions(self):
        with patch.object(app,'clone_audition',return_value=('a','a','ok',{},'reference',False)) as audition:
            self.assertEqual(app.clone_generate('ref.wav','reference',False,'Hello','Calm','English',42,True),('a','a','ok'))
            audition.assert_called_once_with('ref.wav','reference',True,'Hello','Calm','English',42,True)

class SettingsTests(unittest.TestCase):
    def test_defaults_match_model(self):
        import json
        rev=(app.MODEL_REPO/'refs'/'main').read_text().strip()
        defaults=json.loads((app.MODEL_REPO/'snapshots'/rev/'generation_config.json').read_text())
        self.assertEqual(app.generation_options([]),defaults)
    def test_values_and_validation(self):
        values=list(app.SETTING_DEFAULTS);values[1]=1.2;values[5]=False
        self.assertEqual(app.generation_options(values)['temperature'],1.2)
        self.assertFalse(app.generation_options(values)['do_sample'])
        values[3]=2
        with self.assertRaises(ValueError):app.generation_options(values)
    def test_callback_settings_mapping(self):
        cfg=app.build_ui().get_config_file()
        comps={c['id']:c for c in cfg['components']}
        for d in cfg['dependencies']:
            if d.get('api_name') in ['generate','clone_generate']:
                labels=[comps[i]['props'].get('label') for i in d['inputs'][-10:]]
                self.assertEqual(labels,['Maximum new tokens','Temperature','Top-k','Top-p','Repetition penalty','Enable speech sampling','Subtalker temperature','Subtalker top-k','Subtalker top-p','Enable subtalker sampling'])

class AuditRegressionTests(unittest.TestCase):
    def test_compound_lock_blocks_other_thread(self):
        import threading
        attempts=[]
        def load(*a,**kw):
            def other():
                got=app.LOCK.acquire(blocking=False);attempts.append(got)
                if got:app.LOCK.release()
            t=threading.Thread(target=other);t.start();t.join()
            raise RuntimeError('stop before inference')
        with patch.object(app,'load_model',side_effect=load),patch.object(app,'release_model'):
            with self.assertRaisesRegex(Exception,'stop before inference'):
                app.clone_generate('ref.wav','ref',False,'text','','English',42,True)
        self.assertEqual(attempts,[False])

    def test_invalid_settings_before_reference_work(self):
        values=list(app.SETTING_DEFAULTS);values[3]=2
        with patch.object(app,'save_voice') as save:
            with self.assertRaises(ValueError): app.clone_generate('ref.wav','ref',False,'text','','English',42,True,*values)
            save.assert_not_called()
    def test_inference_forwarding_and_blank_note(self):
        import tempfile,json,numpy as np
        from unittest.mock import MagicMock
        fake=MagicMock()
        fake.generate_voice_clone.return_value=([np.zeros(2400)],24000)
        with tempfile.TemporaryDirectory() as tmp,patch.object(app,'OUTPUTS',Path(tmp)),patch.object(app,'load_model',return_value=fake),patch.object(app,'release_model'):
            wav,_,status=app.generate(str(TEST_VOICE),'Hello','','English',42,True,False,*app.SETTING_DEFAULTS)
            self.assertTrue(Path(wav).exists())
            self.assertIn('without delivery instructions',status)
            kwargs=fake.generate_voice_clone.call_args.kwargs
            for k,v in app.generation_options([]).items():self.assertEqual(kwargs[k],v)
            self.assertNotIn('instruct_ids',kwargs)
            self.assertEqual(json.loads(Path(wav).with_suffix('.json').read_text())['generation_settings'],app.generation_options([]))

class CodecBoundsTests(unittest.TestCase):
    def test_column_specific_embedding_bounds(self):
        import tempfile,torch
        from dataclasses import asdict
        item=app.read_voice(str(TEST_VOICE))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bounds.pt'
            data=asdict(item);data['ref_code']=torch.zeros((1,16),dtype=torch.int64)
            data['ref_code'][0,0]=2047
            torch.save({'items':[data]},path)
            app.read_voice(path)
            data['ref_code'][0,0]=2048;torch.save({'items':[data]},path)
            with self.assertRaisesRegex(ValueError,'embedding limits'):app.read_voice(path)
            data['ref_code'][0,0]=0;data['ref_code'][0,1]=2048;torch.save({'items':[data]},path)
            with self.assertRaisesRegex(ValueError,'embedding limits'):app.read_voice(path)

class PreviewVoiceTests(unittest.TestCase):
    def test_exact_preview_snapshot_and_roundtrip(self):
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import Mock
        item=app.read_voice(Path(str(TEST_VOICE)))
        create=Mock(return_value=[item])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);outputs=root/'Outputs';outputs.mkdir();wav=outputs/'take.wav';wav.write_bytes(b'exact preview')
            with patch.object(app,'ROOT',root),patch.object(app,'OUTPUTS',outputs),patch.object(app,'generate',return_value=(str(wav),str(wav),'ok')),patch.object(app,'load_model',return_value=SimpleNamespace(create_voice_clone_prompt=create)),patch.object(app,'release_model'):
                result=app.generate_preview('original.pt',' Exact words. ','Calm','English',42,True,False)
                state=result[3];self.assertEqual(result[4],'Exact words.');self.assertFalse(result[5])
                a,_=app.save_preview_voice(state,True);b,_=app.save_preview_voice(state,True)
                self.assertNotEqual(a,b)
                create.assert_called_with(ref_audio=str(wav.resolve()),ref_text='Exact words.',x_vector_only_mode=False)
                payload=app.torch.load(a,weights_only=True,map_location='cpu')
                self.assertEqual(set(payload),{'items'})
                self.assertEqual(app.read_voice(a).ref_spk_embedding.shape,(2048,))
    def test_preview_guardrails(self):
        import tempfile
        with patch.object(app,'save_voice') as save:
            for state,confirmed in [(None,True),({},False)]:
                with self.assertRaises(Exception):app.save_preview_voice(state,confirmed)
            with tempfile.TemporaryDirectory() as tmp,patch.object(app,'OUTPUTS',Path(tmp)):
                p=Path(tmp)/'a.wav';p.write_bytes(b'changed')
                with self.assertRaisesRegex(Exception,'changed'):app.save_preview_voice({'audio':str(p),'sha256':'wrong','transcript':'old'},True)
            save.assert_not_called()
    def test_preview_wiring_is_server_state(self):
        cfg=app.build_ui().get_config_file();components={c['id']:c for c in cfg['components']}
        save=next(d for d in cfg['dependencies'] if d.get('api_name')=='save_preview_voice')
        self.assertEqual(components[save['inputs'][0]]['type'],'state')
        gen=next(d for d in cfg['dependencies'] if d.get('api_name')=='generate')
        self.assertIn(save['inputs'][0],gen['outputs'])
        self.assertIn(save['inputs'][1],gen['outputs'])

class ConsolidatedUITests(unittest.TestCase):
    def test_original_hidden_and_direct_action_retained(self):
        cfg=app.build_ui().get_config_file()
        tabs=[c['props'] for c in cfg['components'] if c['type']=='tabitem']
        self.assertFalse(next(p for p in tabs if p['label']=='Clone & Generate')['visible'])
        self.assertTrue(next(p for p in tabs if p['label']=='Save / Load Voice')['visible'])
        components={c['id']:c for c in cfg['components']}
        direct=next(d for d in cfg['dependencies'] if d.get('api_name')=='clone_reference_preview')
        self.assertEqual(components[direct['inputs'][1]]['props']['label'],'Reference audio')
        self.assertEqual(components[direct['inputs'][4]]['props']['label'],'Commentary text')
        self.assertTrue(any(d.get('api_name')=='clone_generate' for d in cfg['dependencies']))
    def test_direct_preview_freezes_transcript(self):
        frozen=('a.wav','a.wav','ok',{'transcript':'Reference words','source':'clone_reference'},'Reference words',False)
        with patch.object(app,'clone_audition',return_value=frozen) as audition:
            result=app.clone_generate_preview('ref.wav','Reference words',False,'Test.','Calm','English',42,True)
            self.assertEqual(result,frozen)
            audition.assert_called_once_with('ref.wav','Reference words',True,'Test.','Calm','English',42,True)

class TranscriptToggleTests(unittest.TestCase):
    def test_save_semantics(self):
        with patch.object(app,'save_voice') as save:
            app.save_voice_with_transcript('a.wav','Words',True)
            save.assert_called_with('a.wav','Words',False)
            app.save_voice_with_transcript('a.wav','Words',False)
            save.assert_called_with('a.wav','',True)
    def test_direct_semantics(self):
        for wrapper,target in [(app.clone_with_transcript,'clone_generate'),(app.clone_preview_with_transcript,'clone_generate_preview')]:
            with patch.object(app,target) as gen:
                wrapper('a.wav','Words',True,'Script')
                gen.assert_called_with('a.wav','Words',False,'Script')
                wrapper('a.wav','Words',False,'Script')
                gen.assert_called_with('a.wav','',True,'Script')
        self.assertTrue(app.transcript_visibility(True)['visible'])
        self.assertFalse(app.transcript_visibility(False)['visible'])
    def test_default_and_order(self):
        cfg=app.build_ui().get_config_file();cs=cfg['components']
        toggles=[i for i,c in enumerate(cs) if c['props'].get('label')=='Include reference transcript']
        self.assertEqual(len(toggles),2)
        for i in toggles:
            self.assertTrue(cs[i]['props']['value'])
            self.assertEqual(cs[i+1]['props']['label'],'Reference transcript')

class OutputVisibilityTests(unittest.TestCase):
    def test_files_hidden_until_success(self):
        cfg=app.build_ui().get_config_file()
        for c in cfg['components']:
            if c['props'].get('label') in ['Saved voice file (.pt)','New preview voice (.pt)','Save status','Preview voice save status']:
                self.assertFalse(c['props']['visible'])
        with patch.object(app,'save_voice_with_transcript',return_value=('new.pt','ok')):
            file,status=app.save_voice_display('audio','text',True)
            self.assertTrue(file['visible']);self.assertEqual(file['value'],'new.pt')
            self.assertTrue(status['visible'])
        with patch.object(app,'save_preview_voice',return_value=('preview.pt','ok')):
            file,status=app.save_preview_display({},True)
            self.assertTrue(file['visible']);self.assertEqual(file['value'],'preview.pt')

class CombinedCloneTests(unittest.TestCase):
    def test_one_encoding_same_prompt_and_download(self):
        state={'transcript':'Ref','source':'clone_reference'}
        with patch.object(app,'clone_audition',return_value=('a.wav','a.wav','ok',state,'Ref',False)) as audition,patch.object(app,'save_voice') as save:
            out=app.clone_reference_and_save('ref.wav','Ref',True,'Script','Calm','English',42,True)
        audition.assert_called_once_with('ref.wav','Ref',True,'Script','Calm','English',42,True)
        save.assert_not_called()
        self.assertIsNone(out[6]['value']);self.assertFalse(out[6]['visible'])
        self.assertEqual(out[3],state)

    def test_partial_failure_keeps_new_voice_not_stale_preview(self):
        with patch.object(app,'clone_audition',side_effect=RuntimeError('failure')),patch.object(app,'save_voice') as save:
            out=app.clone_reference_and_save('ref.wav','',False,'Script','','English',42,True)
        save.assert_not_called()
        self.assertIsNone(out[0]);self.assertIsNone(out[3]);self.assertFalse(out[5]);self.assertIsNone(out[6]['value'])
        self.assertFalse(out[6]['visible']);self.assertIn('Audition failed',out[2])

class CompactPreviewTests(unittest.TestCase):
    def test_visibility_and_reset(self):
        self.assertFalse(app.preview_action_visibility(None)[0]['visible'])
        out=app.preview_action_visibility({'transcript':'Frozen'})
        self.assertTrue(out[0]['visible']);self.assertFalse(out[1]['visible']);self.assertFalse(out[2])
    def test_correction_does_not_mutate_snapshot(self):
        original={'transcript':'Frozen','audio':'a.wav','sha256':'hash'}
        with patch.object(app,'save_preview_display') as save:
            app.save_preview_corrected(original,True,'')
            save.assert_called_with(original,True)
            app.save_preview_corrected(original,True,'Actual words',True)
            self.assertEqual(save.call_args.args[0]['transcript'],'Actual words')
            self.assertEqual(original['transcript'],'Frozen')

class CorrectionCheckboxTests(unittest.TestCase):
    def test_toggle_and_inactive_edits(self):
        frozen={'transcript':'Captured words','audio':'a.wav','sha256':'hash'}
        field,confirmed=app.correction_toggle(True,frozen)
        self.assertTrue(field['visible']);self.assertEqual(field['value'],'Captured words');self.assertFalse(confirmed)
        field,_=app.correction_toggle(False,frozen);self.assertFalse(field['visible'])
        with patch.object(app,'save_preview_display') as save:
            app.save_preview_corrected(frozen,True,'Ignored edit',False)
            save.assert_called_with(frozen,True)
            with self.assertRaises(Exception):app.save_preview_corrected(frozen,True,'',True)
        self.assertFalse(app.preview_action_visibility(frozen)[-1])

class CorrectionSnapshotRegression(unittest.TestCase):
    def test_prefill_reset_and_toggle_preserve(self):
        frozen={'transcript':'New take'}
        reset=app.preview_action_visibility(frozen)
        self.assertEqual(reset[1]['value'],'New take')
        self.assertFalse(reset[1]['visible'])
        self.assertFalse(reset[-1])
        for checked in (False,True):
            field,_=app.correction_toggle(checked,frozen,'My corrected words')
            self.assertEqual(field['value'],'My corrected words')
            self.assertEqual(field['visible'],checked)
        self.assertEqual(app.correction_toggle(True,frozen)[0]['value'],'New take')

if __name__=='__main__': unittest.main()

class FirstInteractionRegression(unittest.TestCase):
    def test_preview_controls_reset_in_same_response(self):
        result=('audio','download','ok',{'transcript':'Frozen'},'Frozen',False)
        with patch.object(app,'generate_preview',return_value=result):
            out=app.generate_preview_atomic()
        self.assertEqual(len(out),11)
        self.assertTrue(out[6]['visible'])
        self.assertEqual(out[7]['value'],'Frozen')
        self.assertTrue(out[7]['visible'])
        self.assertFalse(out[-1]['value'])
    def test_no_delayed_preview_state_visibility_callback(self):
        cfg=app.build_ui().get_config_file()
        cs={c['id']:c for c in cfg['components']}
        for d in cfg['dependencies']:
            for component_id,event in d.get('targets',[]):
                self.assertFalse(cs.get(component_id,{}).get('type')=='state' and event=='change' and any('preview' in str(cs.get(out,{}).get('props',{}).get('label','')).lower() for out in d.get('outputs',[])))
    def test_status_notices_are_not_inputs(self):
        cfg=app.build_ui().get_config_file()
        notices=[c for c in cfg['components'] if 'studio-output-status' in c['props'].get('elem_classes',[])]
        self.assertGreaterEqual(len(notices),5)
        self.assertTrue(all(c['type']=='markdown' for c in notices))
        self.assertEqual(app.inspect_voice(None),'')
