"""Bounded, ordered continuous audio sessions over a local WebSocket."""
import asyncio
import base64
import json
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import urlsplit

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import numpy as np
import soundfile as sf
from .segmenter import Segmenter
from .engine import LANGUAGES


def create_server(engine):
    server = FastAPI()
    session_lock = asyncio.Lock()

    @server.get("/live")
    def live_page():
        return FileResponse(Path(__file__).with_name("live.html"))

    @server.websocket("/live/ws")
    async def live_socket(ws: WebSocket):
        origin = urlsplit(ws.headers.get("origin", ""))
        if origin.netloc != ws.headers.get("host") or origin.hostname not in ("localhost", "127.0.0.1"):
            await ws.close(code=1008)
            return
        await ws.accept()
        if session_lock.locked():
            await ws.send_json({"kind": "error", "message": "Another continuous audio session is active."})
            await ws.close()
            return
        async with session_lock:
            cancelled = threading.Event()
            queue = asyncio.Queue(maxsize=3)
            worker = None
            failed = 0
            sequence = 0
            with tempfile.TemporaryDirectory(prefix="index-echo-live-") as temporary:
                try:
                    config = await asyncio.wait_for(ws.receive_json(), timeout=10)
                    target = config.get("target", "ja")
                    maximum = float(config.get("max_seconds", 4))
                    pause = float(config.get("pause_seconds", .35))
                    if target not in LANGUAGES or not 2 <= maximum <= 12 or not .3 <= pause <= 1.5:
                        raise ValueError("Invalid language or segment settings")
                    segmenter = Segmenter(maximum, pause)
                    await ws.send_json({"kind": "status", "message": "Loading the model before audio capture…"})
                    await asyncio.to_thread(engine.prepare)
                    await ws.send_json({"kind": "ready"})
                    if config.get("prepare_only", False):
                        return

                    async def process():
                        nonlocal failed
                        while True:
                            item = await queue.get()
                            if item is None or cancelled.is_set():
                                return
                            number, path, duration, queued_at = item
                            started = time.perf_counter()
                            try:
                                output, details = await asyncio.to_thread(engine.translate, str(path), target)
                                if cancelled.is_set():
                                    return
                                await ws.send_json({
                                    "kind": "audio", "sequence": number,
                                    "audio": base64.b64encode(Path(output).read_bytes()).decode("ascii"),
                                    "details": details, "input_seconds": round(duration, 3),
                                    "processing_seconds": round(time.perf_counter() - started, 3),
                                    "queue_seconds": round(started - queued_at, 3), "pending": queue.qsize(),
                                })
                            except Exception as error:
                                if cancelled.is_set():
                                    return
                                failed += 1
                                try:
                                    await ws.send_json({"kind": "error", "sequence": number, "message": str(error)})
                                except Exception:
                                    cancelled.set()
                                    return
                            finally:
                                path.unlink(missing_ok=True)

                    worker = asyncio.create_task(process())

                    async def submit(segments):
                        nonlocal sequence
                        for segment in segments:
                            if queue.full():
                                await ws.send_json({"kind": "overload", "message":
                                    "Translation cannot keep up. Capture stopped; this last segment was not accepted. Accepted phrases will finish."})
                                return False
                            sequence += 1
                            path = Path(temporary) / f"{sequence}.wav"
                            sf.write(path, segment, Segmenter.rate, subtype="PCM_16")
                            queue.put_nowait((sequence, path, len(segment) / Segmenter.rate, time.perf_counter()))
                            await ws.send_json({"kind": "queued", "sequence": sequence, "pending": queue.qsize()})
                        return True

                    while True:
                        message = await ws.receive()
                        if message["type"] == "websocket.disconnect":
                            raise WebSocketDisconnect()
                        if message.get("bytes") is not None:
                            data = message["bytes"]
                            if len(data) > 16000 * 4 or len(data) % 4:
                                raise ValueError("Invalid audio packet")
                            samples = np.frombuffer(data, dtype="<f4")
                            if not np.isfinite(samples).all():
                                raise ValueError("Audio contains invalid samples")
                            if not await submit(segmenter.feed(samples)):
                                break
                        elif message.get("text"):
                            command = json.loads(message["text"]).get("command")
                            if command == "stop":
                                await submit(segmenter.finish())
                                break
                            if command == "cancel":
                                cancelled.set()
                                break
                    await queue.put(None)
                    await worker
                    if not cancelled.is_set():
                        await ws.send_json({"kind": "done", "failed_phrases": failed})
                except WebSocketDisconnect:
                    cancelled.set()
                except Exception as error:
                    cancelled.set()
                    try:
                        await ws.send_json({"kind": "error", "message": str(error)})
                    except Exception:
                        pass
                finally:
                    cancelled.set()
                    if worker and not worker.done():
                        while not queue.empty():
                            queue.get_nowait()
                        queue.put_nowait(None)
                        try:
                            await worker
                        except Exception:
                            pass
                    try:
                        await ws.close()
                    except Exception:
                        pass
    return server
