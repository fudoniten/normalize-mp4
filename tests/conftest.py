from __future__ import annotations

import sys
import types


if "ffmpeg" not in sys.modules:
    module = types.ModuleType("ffmpeg")

    class Error(Exception):
        def __init__(self, cmd, stdout=None, stderr=None):
            super().__init__(cmd)
            self.cmd = cmd
            self.stdout = stdout
            self.stderr = stderr

    def probe(*args, **kwargs):  # noqa: D401, ARG001
        raise Error("ffprobe", b"", b"ffmpeg-python is not installed")

    module.Error = Error
    module.probe = probe
    sys.modules["ffmpeg"] = module
