from pathlib import Path
import base64
import zlib

# Maple Toolbox v0.23 Public Beta repository loader.
# The source payload is split only because the GitHub connector used to publish
# this initial beta cannot send the full 100 KB Python file in one contents call.
# Reassemble it in memory and execute it exactly as packaged.

payload_dir = Path(__file__).resolve().parent / "payload"
parts = sorted(payload_dir.glob("part*.txt"))

if not parts:
    raise RuntimeError("Maple Toolbox source payload is missing.")

encoded = "".join(p.read_text(encoding="utf-8").strip() for p in parts)
source = zlib.decompress(base64.b64decode(encoded))

exec(compile(source, str(Path(__file__).resolve()), "exec"), globals(), globals())
