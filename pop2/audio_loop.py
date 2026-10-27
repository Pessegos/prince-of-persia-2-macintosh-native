"""Original stone-movement intro and sustain region on SDL's sample clock."""

import ctypes
import hashlib
import wave

import numpy as np


# Optional metadata was absent from older imports. Recognize only the exact
# original cue17 PCM; do not apply its offsets to another sound of similar size.
LEGACY_GATE_PCM = '235bf026660e45b488948d9dfcca6eaa493b1d15cf43ee2a75e3f1f6b39e6178'


def gate_loop_bounds(path, metadata, output_rate):
    with wave.open(str(path)) as reader:
        rate, frames = reader.getframerate(), reader.getnframes()
        loop = metadata.get('loop')
        if loop is None:
            if (reader.getnchannels(), reader.getsampwidth(), rate, frames) != (1, 2, 11025, 11524):
                return None
            pcm = reader.readframes(frames)
            if hashlib.sha256(pcm).hexdigest() != LEGACY_GATE_PCM:
                return None
            loop = dict(rate=11025, start=5025, end=11520, count=65535)
        if (loop.get('count') != 65535 or loop.get('rate') != rate
                or not isinstance(loop.get('start'), int) or not isinstance(loop.get('end'), int)
                or not 0 <= loop['start'] < loop['end'] <= frames):
            raise ValueError('Invalid stone-movement sustain loop; import the game again')
        return round(loop['start'] * output_rate / rate), round(loop['end'] * output_rate / rate)


class PcmSustain:
    def __init__(self, library, raw, channels, start, end):
        self.library, self.channels = library, channels
        self.samples = np.frombuffer(raw, dtype=np.int16).reshape(-1, channels)
        if not 0 <= start < end <= len(self.samples):
            raise ValueError('Stone-movement loop is outside the loaded PCM')
        self.start_frame, self.end_frame = start, end
        self.positions = {}
        callback_type = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_void_p,
                                        ctypes.c_int, ctypes.c_void_p)
        done_type = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_void_p)
        self.callback = callback_type(self.process)
        self.done_callback = done_type(self.finished)

    def start(self, channel):
        # MixerPlayback stops the carrier channel first. Register before play,
        # so the very first audio buffer begins at frame zero, without a race.
        self.cancel(channel)
        self.positions[channel] = 0
        if not self.library.Mix_RegisterEffect(
                channel, self.callback, ctypes.cast(self.done_callback, ctypes.c_void_p), None):
            self.finished(channel, None)
            raise RuntimeError('Cannot apply the stone-movement sustain loop')

    def cancel(self, channel):
        if channel in self.positions:
            self.library.Mix_UnregisterEffect(channel, self.callback)
            self.finished(channel, None)

    def finished(self, channel, _user):
        self.positions.pop(channel, None)

    def fill(self, samples, position):
        written = 0
        while written < len(samples):
            count = min(len(samples) - written, self.end_frame - position)
            samples[written:written + count] = self.samples[position:position + count]
            written += count
            position += count
            if position == self.end_frame:
                position = self.start_frame
        return position

    def process(self, channel, stream, length, _user):
        position = self.positions.get(channel)
        if position is None:
            return
        pcm = (ctypes.c_int16 * (length // 2)).from_address(stream)
        samples = np.ctypeslib.as_array(pcm).reshape(-1, self.channels)
        self.positions[channel] = self.fill(samples, position)

    def close(self):
        for channel in tuple(self.positions):
            self.cancel(channel)
