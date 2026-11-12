"""Stable playback props for dynamic Gradio batch cards."""
import gradio as gr


class BatchAudio(gr.Audio):
    """Retain mounted media when another clip changes (Gradio 6.17 compatibility)."""
    is_template = True
    preserve_media = False

    @classmethod
    def get_component_class_id(cls):
        return gr.Audio.get_component_class_id()

    def get_config(self, cls=None):
        config = super().get_config(gr.Audio)
        if self.preserve_media:
            # Gradio's Audio wrapper merges supplied props into its retained
            # state. Re-sending these triggers WaveSurfer.load()/stop(), even
            # for an unchanged URL. New/remounted takes still get full props.
            for prop in ('value', 'playback_position', 'waveform_options'):
                config.pop(prop, None)
        return config
