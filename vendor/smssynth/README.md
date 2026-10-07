# MIDI Renderer

Unmodified `smssynth.exe` from resource_dasm v2026-09-03:
https://github.com/fuzziqersoftware/resource_dasm/releases/tag/v2026-09-03

Executable SHA-256:
`46cdca8c3c6d18e3912e1aee709b4f6c9e222da211c3ac6b125262a46a614359`

Upstream source and build instructions:
https://github.com/fuzziqersoftware/resource_dasm

The renderer links the upstream phosg utility library:
https://github.com/fuzziqersoftware/phosg

`libc++.dll` and `libunwind.dll` are the x86-64 runtime libraries from
llvm-mingw 20260922 (UCRT):
https://github.com/mstorsjo/llvm-mingw/releases/tag/20260922

License notices are included alongside the binaries. These are tools, not
original game files. They render the user's locally imported instruments and
MIDI during setup; no synthesizer process is started during gameplay.
