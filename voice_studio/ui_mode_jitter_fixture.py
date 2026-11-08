import app
ui=app.build_ui()
import numpy as np
import soundfile as sf
p=app.ROOT/'Temp'/'mode-jitter-tone.wav'
sf.write(p,0.1*np.sin(2*np.pi*220*np.arange(48000)/24000),24000)
for component in ui.blocks.values():
    if isinstance(component,app.gr.Audio) and component.label=='Reference audio':
        component.value={'path':str(p),'url':'/gradio_api/file='+str(p),'orig_name':p.name,'size':p.stat().st_size,'meta':{'_type':'gradio.FileData'}}
with ui:
    ui.load(fn=None,js="""() => {
      document.querySelector('#voice-mode-tabs').addEventListener('click',()=>{
        const samples=[];let n=0;
        function sample(){const r=document.querySelector('#reference-panel'),p=r.querySelector('.studio-reference-audio'),f=r.querySelector('.form');
          samples.push({w:Math.round(r.getBoundingClientRect().width),p:Math.round(p.getBoundingClientRect().height),y:Math.round(f.getBoundingClientRect().top),body:Math.round(p.querySelector('.audio-container')?.getBoundingClientRect().height||0)});
          if(++n<60)requestAnimationFrame(sample);else document.querySelector('#voice-mode-tabs').dataset.trace=JSON.stringify(samples);
        }requestAnimationFrame(sample);
      });
    }""")
ui.queue().launch(server_name='127.0.0.1',server_port=8004,share=False,inbrowser=False,css=(app.ROOT/'theme.css').read_text(),allowed_paths=[str(app.ROOT/'assets'),str(p)],footer_links=['api','settings'])
