"""Runs BalatroBot's patched server.lua under LuaJIT (via lupa) with a fake socket.

Needs `pip install lupa` and a BalatroBot checkout; set BALATROBOT_SRC to the
checkout (default: ../coder/balatrobot next to this repo). Skipped otherwise.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from patches.patch_balatrobot import MARKER, patch_text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get("BALATROBOT_SRC",
                     os.path.join(ROOT, "..", "coder", "balatrobot"))
SERVER = os.path.join(SRC, "src", "lua", "core", "server.lua")

try:
    from lupa import luajit21 as lupa
except ImportError:
    lupa = None


def _to_py(lua, value):
    if lupa.lua_type(value) == "table":
        keys = list(value.keys())
        if keys and all(isinstance(k, int) for k in keys):
            return [_to_py(lua, value[k]) for k in sorted(keys)]
        return {k: _to_py(lua, v) for k, v in value.items()}
    return value


def _to_lua(lua, value):
    if isinstance(value, dict):
        return lua.table_from({k: _to_lua(lua, v) for k, v in value.items()})
    if isinstance(value, list):
        return lua.table_from([_to_lua(lua, v) for v in value])
    return value


class Server:
    """Loads server.lua with stubbed globals and feeds it raw HTTP requests."""

    def __init__(self, source):
        self.lua = lua = lupa.LuaRuntime(unpack_returned_tuples=True)
        g = lua.globals()
        g.py_decode = lambda s: _to_lua(lua, json.loads(s))
        g.py_encode = lambda t: json.dumps(_to_py(lua, t))
        lua.execute('''
            package.preload.socket = function() return {} end
            package.preload.json = function()
              return { decode = function(s) return py_decode(s) end,
                       encode = function(t) return py_encode(t) end }
            end
            local noop = function() end
            sendDebugMessage, sendErrorMessage, sendWarnMessage = noop, noop, noop
            BB_SETTINGS = { host = "127.0.0.1", port = 12346 }
            BB_ERROR_NAMES = { BAD_REQUEST = "BAD_REQUEST", INTERNAL_ERROR = "INTERNAL_ERROR",
                               INVALID_STATE = "INVALID_STATE" }
            BB_ERROR_CODES = { BAD_REQUEST = -32001, INTERNAL_ERROR = -32000,
                               INVALID_STATE = -32002 }
        ''')
        lua.execute(source)
        self.dispatched = []
        g.py_dispatched = self.dispatched.append
        lua.execute('''
            DISPATCHER = { dispatch = function(req)
              py_dispatched(req.method)
              BB_SERVER.send_response({ status = "ok" })
            end }
        ''')

    def request(self, raw):
        lua = self.lua
        lua.globals().RAW = raw
        return lua.execute('''
            local sent = {}
            local client = {
              receive = function() if RAW then local d = RAW; RAW = nil; return d end
                                   return nil, "timeout" end,
              send = function(_, s) table.insert(sent, s) return #s end,
              settimeout = function() end,
              close = function() end,
            }
            local accepted = false
            BB_SERVER.server_socket = { accept = function()
              if accepted then return nil, "timeout" end
              accepted = true
              return client
            end }
            BB_SERVER.client_socket = nil
            BB_SERVER.update(DISPATCHER)
            return table.concat(sent)
        ''')


def http(headers, body='{"jsonrpc": "2.0", "method": "health", "id": 1}'):
    lines = ["POST / HTTP/1.1"] + [f"{k}: {v}" for k, v in headers.items()]
    lines.append(f"Content-Length: {len(body)}")
    return "\r\n".join(lines) + "\r\n\r\n" + body


GOOD = {"Host": "127.0.0.1:12346", "Content-Type": "application/json"}


@unittest.skipUnless(lupa and os.path.isfile(SERVER), "needs lupa and a BalatroBot checkout")
class PatchedServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SERVER, encoding="utf-8") as f:
            cls.original = f.read()
        cls.patched = patch_text(cls.original)

    def status(self, server, headers):
        resp = server.request(http(headers))
        return int(resp.split(" ", 2)[1])

    def test_patch_is_marked_and_idempotent_check(self):
        self.assertIn(MARKER, self.patched)
        self.assertNotIn(MARKER, self.original)
        with self.assertRaises(ValueError):
            patch_text(self.patched)  # anchors already rewritten

    def test_crlf_files(self):
        crlf = patch_text(self.original.replace("\n", "\r\n"))
        self.assertEqual(crlf.replace("\r\n", "\n"), self.patched)

    def test_original_accepts_browser_request(self):
        server = Server(self.original)
        browser = {"Host": "127.0.0.1:12346", "Content-Type": "text/plain",
                   "Origin": "https://evil.example"}
        self.assertEqual(self.status(server, browser), 200)
        self.assertEqual(server.dispatched, ["health"])

    def test_patched_allows_api_clients(self):
        server = Server(self.patched)
        for headers in [GOOD,
                        {"Host": "localhost:12346", "Content-Type": "application/json"},
                        {"Host": "[::1]:12346", "Content-Type": "application/json; charset=utf-8"}]:
            self.assertEqual(self.status(server, headers), 200, headers)
        self.assertEqual(server.dispatched, ["health"] * 3)

    def test_patched_rejects_browser_style_requests(self):
        server = Server(self.patched)
        cases = [
            {**GOOD, "Origin": "https://evil.example"},                 # cross-site page
            {**GOOD, "Origin": "null"},                                  # sandboxed iframe
            {"Host": "127.0.0.1:12346", "Content-Type": "text/plain"},   # no-preflight POST
            {"Host": "evil.example:12346", "Content-Type": "application/json"},  # rebinding
            {"Content-Type": "application/json"},                        # no Host
        ]
        for headers in cases:
            resp = server.request(http(headers))
            self.assertTrue(resp.startswith("HTTP/1.1 403 Forbidden"), (headers, resp[:40]))
        self.assertEqual(server.dispatched, [])


if __name__ == "__main__":
    unittest.main()
