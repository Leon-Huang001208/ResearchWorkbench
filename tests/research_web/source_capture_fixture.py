"""No-network real stdlib HTTPResponse fixtures at the actual worker boundary."""

import http.client
import io
import socket
from datetime import UTC, datetime, timedelta
from itertools import count
from urllib.parse import urlsplit

import pytest

from app.research_web import research_web_sources as reader

_CAPTURE_CLOCK = datetime(2026, 10, 28, tzinfo=UTC)
_CAPTURE_TICKS = count()


def offline_http(monkeypatch, wire):
    """Install a same-process worker with actual response parsing and network guards."""

    class CaptureClock(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = _CAPTURE_CLOCK + timedelta(microseconds=next(_CAPTURE_TICKS))
            return instant.astimezone(tz) if tz is not None else instant.replace(tzinfo=None)

    monkeypatch.setattr(reader, "datetime", CaptureClock)
    original_connect = socket.socket.connect
    original_http = http.client.HTTPConnection.connect
    original_https = http.client.HTTPSConnection.connect

    def local_socket(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            pytest.fail("offline source test attempted a network connection")
        return original_connect(sock, address)

    def local_http(connection):
        if connection.host not in {"127.0.0.1", "::1", "localhost"}:
            pytest.fail("offline source test attempted HTTP")
        return original_http(connection)

    def local_https(connection):
        if connection.host not in {"127.0.0.1", "::1", "localhost"}:
            pytest.fail("offline source test attempted HTTPS")
        return original_https(connection)

    monkeypatch.setattr(socket.socket, "connect", local_socket)
    monkeypatch.setattr(http.client.HTTPConnection, "connect", local_http)
    monkeypatch.setattr(http.client.HTTPSConnection, "connect", local_https)
    responses = []

    class Socket:
        def makefile(self, *_args):
            return io.BytesIO(wire)

    class Connection:
        sock = None

        def __init__(self, *_args):
            self.response = None

        def request(self, method, *_args, **_kwargs):
            assert method == "GET"

        def getresponse(self):
            self.response = http.client.HTTPResponse(Socket())
            self.response.begin()
            responses.append(self.response)
            return self.response

        def close(self):
            if self.response is not None:
                self.response.close()

    def public(url):
        assert urlsplit(url).scheme == "https"
        return urlsplit(url).hostname, ["203.0.113.1"]

    async def worker(url):
        return reader.fetch_document(url)

    monkeypatch.setattr(reader, "public_target", public)
    monkeypatch.setattr(reader, "PublicConnection", Connection)
    monkeypatch.setattr(reader, "fetch_owned_document", worker)
    return responses


def fixed_response(body, *, length=None):
    size = len(body) if length is None else length
    return (
        b"HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: "
        + str(size).encode()
        + b"\r\n\r\n"
        + body
    )
