"""Pause-aware segmentation of 16 kHz mono PCM for utterance dubbing."""
from collections import deque
import numpy as np
import webrtcvad


class Segmenter:
    rate = 16000
    frame_size = 320

    def __init__(self, max_seconds=6, pause_seconds=0.5, sensitivity=2):
        self.vad = webrtcvad.Vad(sensitivity)
        self.max_frames = int(max_seconds / 0.02)
        self.pause_frames = int(pause_seconds / 0.02)
        self.pending = np.zeros(0, dtype=np.float32)
        self.preroll = deque(maxlen=10)
        self.frames = []
        self.silence = 0
        self.speech_frames = 0

    def _flush(self, trim=True):
        frames, speech = self.frames, self.speech_frames
        if trim and self.silence > 5:
            frames = frames[:-(self.silence - 5)]
        self.frames = []
        self.silence = self.speech_frames = 0
        # Ignore clicks and very short fragments.
        return np.concatenate(frames) if frames and speech >= 10 else None

    def feed(self, samples):
        self.pending = np.concatenate((self.pending, np.asarray(samples, dtype=np.float32)))
        result = []
        offset = 0
        while len(self.pending) - offset >= self.frame_size:
            frame = self.pending[offset:offset+self.frame_size].copy()
            offset += self.frame_size
            pcm = (np.clip(frame, -1, 1) * 32767).astype('<i2').tobytes()
            voiced = self.vad.is_speech(pcm, self.rate)
            if not self.frames:
                if not voiced:
                    self.preroll.append(frame)
                    continue
                self.frames = list(self.preroll)
                self.preroll.clear()
            self.frames.append(frame)
            self.speech_frames += int(voiced)
            self.silence = 0 if voiced else self.silence + 1
            if self.silence >= self.pause_frames or len(self.frames) >= self.max_frames:
                segment = self._flush()
                if segment is not None:
                    result.append(segment)
        self.pending = self.pending[offset:].copy()
        return result

    def finish(self):
        if self.frames and len(self.pending):
            self.frames.append(self.pending)
        self.pending = np.zeros(0, dtype=np.float32)
        segment = self._flush()
        self.preroll.clear()
        return [segment] if segment is not None else []
