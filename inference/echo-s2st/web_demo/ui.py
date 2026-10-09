"""Gradio clip interface and continuous audio transport on one local server."""
import os
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import gradio as gr
from .live_backend import create_server


def create_app(engine):
    server = create_server(engine)
    with gr.Blocks(title="Index-Echo speech translation") as demo:
        gr.Markdown(f"# Index-Echo {engine.size.upper()} speech translation\n"
                    "Upload or record up to 30 seconds of English or Chinese audio. "
                    "The standard model generates translated speech using the source voice as a reference.")
        gr.Markdown("[Open continuous microphone or browser-audio demo](/live)\n\n"
                    "First use downloads the official model. Continuous translation can fall behind; "
                    "this demo processes complete phrases rather than partial speech tokens.")
        audio = gr.Audio(sources=["upload", "microphone"], type="filepath", format="wav", label="Source speech")
        with gr.Row():
            english = gr.Button("Load bundled English sample")
            chinese = gr.Button("Load bundled Chinese sample")
        target = gr.Dropdown(choices=[("Japanese", "ja"), ("Spanish", "es"), ("Chinese", "zh"), ("English", "en")],
                             value="ja", label="Target language")
        translate = gr.Button("Translate speech", variant="primary")
        output = gr.Audio(label="Translated speech", type="filepath")
        details = gr.JSON(label="Transcript, translation and timing")
        with gr.Row():
            prepare = gr.Button("Get model ready")
            unload = gr.Button("Unload model and release GPU memory")
        status = gr.Textbox(label="Model status", interactive=False)
        english.click(lambda: engine.sample("en"), outputs=audio, api_name="sample_english")
        chinese.click(lambda: engine.sample("zh"), outputs=audio, api_name="sample_chinese")
        translate.click(engine.translate, [audio, target], [output, details], concurrency_limit=1, api_name="translate")
        prepare.click(engine.prepare, outputs=status, api_name="prepare")
        unload.click(engine.unload, outputs=status, api_name="unload")
    return gr.mount_gradio_app(server, demo.queue(), path="/")
