"""Prepare native game samples and MIDI music for local playback."""

from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import wave

import mido
import numpy as np

from pop2.audio_formats import digitized_sound, mohawk_resources, standard_sound
from pop2.mac_resources import get_data_fork, parse_resource_fork, _span
from tools.extract_enemy_profiles import expand_a5_data


AUDIO_SCHEMA = 1
LEVEL_ONE_SONGS = (6, 32, 38, 39, 40, 41, 42, 43, 64)
DESERT_SONGS = (46, 47, 48, 49, 50)
CAVERN_SONGS = (24, 62, 63, 71, 279, 285, 297, *range(73, 109))
# Levels 4-5: Float (111), Chase (112), the flying-carpet room and ride
# (114-116) and the bridge fight, room-7 door and collapse (119-121).
LATE_CAVERN_SONGS = (111, 112, 114, 115, 116, 119, 120, 121)
# Levels 6-7 (environment 4): ambient bank 4 (139-174), the ruins' end song
# (GetEndSong 5:4e32, 124) and FindSwd (183). Rendered, not yet required.
# The ruins: ambient 139-174, the level end 124, 183; the flip flask 176/177;
# the heads' InjrHead 136 and KillHead 137; level nine's Horse 185 and Chasm 292;
# level eight's throne: SeeThron 179, Throne1 180, Throne2 181 and Throne4 182.
RUINS_SONGS = (*range(139, 175), 124, 183, 176, 177, 136, 137, 185, 292, *range(179, 183))
SYNTH_DIR = Path(__file__).resolve().parents[1] / "vendor" / "smssynth"


def audio_tables(program):
    a5 = expand_a5_data(program)

    def words(offset, count):
        return list(struct.unpack(f">{count}h", _span(a5, len(a5) + offset, count * 2)))

    cues = {}
    for index in range(301):
        mode, priority, _handle, kind = words(-0x40a0 + index * 8, 4)
        if kind >= 0:
            cues[str(index)] = {"mode": mode, "priority": priority,
                                "kind": "midi" if kind == 0 else "pcm"}
    ambient = []
    for bank in range(7):
        starts_at = struct.unpack_from(">i", a5, len(a5) - 0x40fe + bank * 4)[0]
        counts_at = struct.unpack_from(">i", a5, len(a5) - 0x40e2 + bank * 4)[0]
        groups = (counts_at - starts_at) // 2 if starts_at and counts_at else 0
        if not 0 <= groups <= 3:
            raise ValueError("Invalid ambient music table")
        ambient.append({"starts": words(starts_at, groups) if groups else [],
                        "counts": words(counts_at, groups) if groups else [],
                        "combat_group": words(-0x40c6 + bank * 2, 1)[0]})
    return {"schema": AUDIO_SCHEMA, "cues": cues,
            "death_cues": words(-0x4396, 16), "ambient": ambient}


def instrument_bank(program, directory):
    instruments = []
    for resource_id, resource in sorted(program["INST"].items()):
        data = resource["data"]
        sound_id, base_note = struct.unpack(">hH", _span(data, 0, 4))
        flags1, flags2 = _span(data, 5, 2)
        if struct.unpack(">H", _span(data, 12, 2))[0] != 0:
            raise ValueError("Split instrument banks are not supported")
        sample = standard_sound(program["snd "][sound_id]["data"])
        filename = f"instrument-{resource_id}.wav"
        (directory / filename).write_bytes(sample.wav(sustain=not flags1 & 0x20))
        constant = bool(flags2 & 0x40)
        region_note = 60 if constant else base_note
        note = (region_note + sample.base_note - 60 if region_note and sample.base_note
                else region_note or sample.base_note or 60)
        region = {"key_low": 0, "key_high": 127, "base_note": note,
                  "filename": filename}
        if not flags1 & 0x08:
            region["freq_mult"] = 22050 / sample.rate
        if constant:
            region["constant_pitch"] = True
        instruments.append({"id": resource_id, "regions": [region]})
    environment = {"sequence_type": "MIDI", "sequence_filename": "",
                   "allow_program_change": True, "instruments": instruments}
    (directory / "instruments.json").write_text(json.dumps(environment), encoding="ascii")


def render_midi(directory, filename, output, synth_dir=SYNTH_DIR, *, work=""):
    """Render `filename` to the WAV `output`; returns the playback duration.

    `work` prefixes the renderer's working files, so renders into one
    directory can run at the same time; those prefixed files are removed.
    """
    executable = Path(synth_dir) / "smssynth.exe"
    if not executable.is_file():
        raise ValueError("The bundled MIDI renderer is missing (vendor/smssynth)")
    env = os.environ.copy()
    env["PATH"] = str(Path(synth_dir).resolve()) + os.pathsep + env.get("PATH", "")
    constant = mido.MidiFile(type=0, ticks_per_beat=1000)
    track = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=1000000)])
    constant.tracks.append(track)
    seconds, previous = 0.0, 0
    for message in mido.MidiFile(directory / filename):
        seconds += message.time
        if message.type == "set_tempo":
            continue
        tick = round(seconds * 1000)
        track.append(message.copy(time=tick - previous))
        previous = tick
    # At 48 kHz a 1 ms pulse is exactly 48 frames. This avoids upstream's
    # integer BPM and samples-per-pulse truncation without changing pitches.
    playback, synthesis = f"{work}playback.mid", f"{work}synthesis.wav"
    constant.save(directory / playback)
    try:
        result = subprocess.run(
            [str(executable.resolve()), playback, "--json-environment=instruments.json",
             f"--output-filename={synthesis}", "--sample-rate=48000"],
            cwd=directory, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=120,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError("MIDI rendering timed out; the previous installation is unchanged") from error
    if result.returncode:
        raise ValueError("MIDI rendering failed: " + result.stderr[-1000:].decode("utf-8", "replace"))
    # This upstream build writes oversized RIFF lengths. Read the actual float
    # payload, then emit a conventional PCM WAV accepted by SDL and wave.
    if work:
        (directory / playback).unlink()
    data = (directory / synthesis).read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Invalid synthesized WAV header")
    cursor = 12
    samples = None
    while cursor + 8 <= len(data):
        tag, size = struct.unpack_from("<4sI", data, cursor)
        if tag == b"data":
            samples = np.frombuffer(data[cursor + 8:], dtype="<f4")
            break
        cursor += 8 + size + (size & 1)
    if samples is None or len(samples) % 2 or not np.isfinite(samples).all():
        raise ValueError("Invalid synthesized waveform")
    # Shared headroom, not per-song normalization: preserve relative dynamics.
    peak = float(np.max(np.abs(samples), initial=0))
    if peak > 4:
        raise ValueError(f"Unexpected MIDI output level: {peak:.3f}")
    pcm = np.rint(samples * 8191).astype("<i2").tobytes()
    with wave.open(str(directory / output), "wb") as writer:
        writer.setparams((2, 2, 48000, 0, "NONE", ""))
        writer.writeframes(pcm)
    (directory / synthesis).unlink()
    return len(samples) / 96000


def extract_audio(image, program_bytes, prince_bytes, directory, progress=lambda _text: None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    program = parse_resource_fork(program_bytes)
    manifest = audio_tables(program)
    instrument_bank(program, directory)
    midi = mohawk_resources(get_data_fork(image, "MIDISnd.dat"))["MIDI"]
    pcm = mohawk_resources(get_data_fork(image, "DigiSnd.dat"))["snd "]
    songs = []
    for cue, entry in manifest["cues"].items():
        resource_id = 9752 + int(cue)
        if entry["kind"] == "pcm":
            if resource_id not in pcm:
                continue
            sample = digitized_sound(pcm[resource_id])
            entry["file"] = f"cue-{cue}.wav"
            # PCM shares the same 12 dB of headroom as the MIDI rendering.
            values = np.frombuffer(sample.pcm, dtype=np.uint8).astype(np.int16) - 128
            encoded = (values * 64).astype("<i2").tobytes()
            with wave.open(str(directory / entry["file"]), "wb") as writer:
                writer.setparams((sample.channels, 2, sample.rate, 0, "NONE", ""))
                writer.writeframes(encoded)
            entry["duration"] = len(sample.pcm) / sample.channels / sample.rate
        elif resource_id in midi:
            raw_name = f"cue-{cue}.mid"
            raw = midi[resource_id]
            (directory / raw_name).write_bytes(raw)
            sequence = mido.MidiFile(file=io.BytesIO(raw))
            entry["duration"] = sequence.length
            entry["name"] = next((message.name for track in sequence.tracks for message in track
                                   if message.type == "track_name"), "")
            if int(cue) in LEVEL_ONE_SONGS + DESERT_SONGS + CAVERN_SONGS + LATE_CAVERN_SONGS + RUINS_SONGS:
                entry["file"] = f"cue-{cue}.wav"
                songs.append((entry, raw_name))
    # Each song is a separate renderer process: render them side by side.
    with ThreadPoolExecutor(os.cpu_count() or 1) as pool:
        durations = pool.map(lambda song: render_midi(directory, song[1], song[0]["file"],
                                                      work=f"{song[1]}."), songs)
        for (entry, _raw_name), duration in zip(songs, durations):
            progress(f"Preparing music: {entry['name']}")
            entry["playback_duration"] = duration
    level = parse_resource_fork(prince_bytes)["LEVL"][2000]["data"]
    manifest["level_one"] = {
        "bank": struct.unpack_from(">h", level, 0x2186)[0],
        "groups": list(struct.unpack_from(">960h", level, 0x424a)),
    }
    required = set(LEVEL_ONE_SONGS + DESERT_SONGS + CAVERN_SONGS + LATE_CAVERN_SONGS) | {7, 8, 9, 10, 11, 12, 13, 14, 30, 31, 34, 35, 36, 294, 295, 296}
    missing = sorted(cue for cue in required if not manifest["cues"].get(str(cue), {}).get("file"))
    if missing:
        raise ValueError(f"Game audio is incomplete (missing cues: {missing})")
    (directory / "playback.mid").unlink(missing_ok=True)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="ascii")
    return manifest
