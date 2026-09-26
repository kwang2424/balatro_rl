"""Harden your local BalatroBot mod against requests from web pages.

BalatroBot's HTTP server accepts any POST to 127.0.0.1:12346. A web page open
in your browser can send one too (a "simple" cross-site POST needs no CORS
preflight), and could then call `save`/`screenshot` to write files to any path.
DNS rebinding can also get around the localhost binding.

This patch makes the server reject a request unless all of these hold:
  - no Origin header (browsers add one to cross-site POSTs; API clients don't)
  - Host is 127.0.0.1 / localhost / ::1 (or the configured BALATROBOT_HOST)
  - Content-Type is application/json (a browser must preflight this, and the
    server refuses the preflight)

The Python client in this repo, BalatroBot's own CLI, and the curl examples in
their docs all pass these checks.

Usage (point it at the installed mod folder, the one containing balatrobot.json):
    python patches/patch_balatrobot.py "%AppData%/Balatro/Mods/balatrobot"
    python patches/patch_balatrobot.py <mod_dir> --check    # report status only
    python patches/patch_balatrobot.py <mod_dir> --revert   # restore the backup

Tested against BalatroBot v1.5.2. Re-run it after updating the mod.
"""

import argparse
import os
import shutil
import sys

MARKER = "balatro_rl local patch"
SERVER = os.path.join("src", "lua", "core", "server.lua")

CHECK_FUNCTION = '''--- Reject requests that don't come from a local API client ({marker}).
--- Browsers send Origin on cross-site POSTs and can't send application/json
--- without a preflight (which this server refuses); checking Host blocks DNS
--- rebinding.
---@param request table Parsed HTTP request
---@return boolean ok
---@return string? reason
local function check_local_client(request)
  local headers = request.headers or {{}}
  if headers["origin"] then
    return false, "Requests from web pages are not allowed"
  end

  local host = (headers["host"] or ""):lower()
  local name = host:match("^%[(.-)%]") or host:match("^([^:]+)") or ""
  local configured = tostring(BB_SERVER.host or ""):lower()
  if name ~= "127.0.0.1" and name ~= "localhost" and name ~= "::1" and name ~= configured then
    return false, "Invalid Host header"
  end

  local content_type = (headers["content-type"] or ""):lower()
  if not content_type:find("^application/json") then
    return false, "Content-Type must be application/json"
  end

  return true
end

--- Handle parsed HTTP request'''.format(marker=MARKER)

EDITS = [
    # (anchor, replacement)
    ('    [400] = "Bad Request",\n',
     '    [400] = "Bad Request",\n    [403] = "Forbidden",\n'),
    ("--- Handle parsed HTTP request", CHECK_FUNCTION),
    ("  handle_jsonrpc(request.body, dispatcher)\nend",
     "  local allowed, reason = check_local_client(request)\n"
     "  if not allowed then\n"
     "    send_http_error(403, reason)\n"
     "    return\n"
     "  end\n"
     "\n"
     "  handle_jsonrpc(request.body, dispatcher)\nend"),
]


def patch_text(text):
    """Return patched server.lua text. Raises ValueError if it doesn't match."""
    if MARKER in text:
        raise ValueError("already patched")
    crlf = "\r\n" in text
    if crlf:
        text = text.replace("\r\n", "\n")
    for anchor, _ in EDITS:
        n = text.count(anchor)
        if n != 1:
            raise ValueError(f"expected 1 match for {anchor.strip()[:40]!r}, found {n}")
    for anchor, replacement in EDITS:
        text = text.replace(anchor, replacement)
    return text.replace("\n", "\r\n") if crlf else text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mod_dir", help="BalatroBot mod folder (contains balatrobot.json)")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="only report whether it's patched")
    group.add_argument("--revert", action="store_true", help="restore server.lua from the backup")
    args = ap.parse_args(argv)

    path = os.path.join(os.path.expanduser(os.path.expandvars(args.mod_dir)), SERVER)
    backup = path + ".orig"
    if not os.path.isfile(path):
        print(f"not found: {path}\nPass the BalatroBot mod folder.", file=sys.stderr)
        return 1

    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    patched = MARKER in text

    if args.check:
        print("patched" if patched else "not patched")
        return 0

    if args.revert:
        if not os.path.isfile(backup):
            print(f"no backup at {backup}", file=sys.stderr)
            return 1
        shutil.copyfile(backup, path)
        os.remove(backup)
        print("restored original server.lua")
        return 0

    if patched:
        print("already patched")
        return 0

    try:
        new_text = patch_text(text)
    except ValueError as e:
        print(f"server.lua doesn't match the version this patch was written for ({e}).\n"
              f"Nothing was changed.", file=sys.stderr)
        return 1

    shutil.copyfile(path, backup)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(new_text)
    print(f"patched {path}\nbackup at {backup}\nrestart Balatro for it to take effect")
    return 0


if __name__ == "__main__":
    sys.exit(main())
