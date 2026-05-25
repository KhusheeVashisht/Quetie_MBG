"""
Tests for Twitch command handlers.
"""

from quetie.twitch_bot.handlers import CommandHandlers


class FakeIRCClient:
    def __init__(self):
        self.handlers = {}
        self.messages = []

    def register_handler(self, command, handler):
        self.handlers[command] = handler

    def send_message(self, message):
        self.messages.append(message)


def test_handle_add_multiple_urls(monkeypatch):
    client = FakeIRCClient()
    handlers = CommandHandlers(client)
    calls = []

    def fake_add_to_queue(url, submitter_username, notes=None):
        calls.append((url, submitter_username, notes))
        return True, f"Added to queue (position {len(calls)})", len(calls)

    monkeypatch.setattr("quetie.twitch_bot.handlers.queue_manager.add_to_queue", fake_add_to_queue)

    handlers.handle_add("miss_brain_glitch", "https://one.example/video\nhttps://two.example/video\nhttps://three.example/video")

    assert len(calls) == 3
    assert calls[0][0] == "https://one.example/video"
    assert calls[1][0] == "https://two.example/video"
    assert calls[2][0] == "https://three.example/video"
    assert client.messages == ["@miss_brain_glitch Queued 3 links at positions: 1, 2, 3"]


def test_handle_add_duplicate_url_is_rejected(monkeypatch):
    client = FakeIRCClient()
    handlers = CommandHandlers(client)
    calls = []

    def fake_add_to_queue(url, submitter_username, notes=None):
        calls.append((url, submitter_username, notes))
        if len(calls) == 1:
            return True, "Added to queue (position 1)", 1
        return False, "This link is already in the queue", None

    monkeypatch.setattr("quetie.twitch_bot.handlers.queue_manager.add_to_queue", fake_add_to_queue)

    handlers.handle_add("miss_brain_glitch", "https://one.example/video https://one.example/video")

    assert len(calls) == 2
    assert client.messages == [
        "@miss_brain_glitch Queued 1/2 links (positions: 1); https://one.example/video: This link is already in the queue - not added"
    ]


def test_handle_add_single_url_preserves_notes(monkeypatch):
    client = FakeIRCClient()
    handlers = CommandHandlers(client)
    calls = []

    def fake_add_to_queue(url, submitter_username, notes=None):
        calls.append((url, submitter_username, notes))
        return True, "Added to queue (position 1)", 1

    monkeypatch.setattr("quetie.twitch_bot.handlers.queue_manager.add_to_queue", fake_add_to_queue)

    handlers.handle_add("miss_brain_glitch", "https://one.example/video great song")

    assert calls == [("https://one.example/video", "miss_brain_glitch", "great song")]
    assert client.messages == ["@miss_brain_glitch Added to queue (position 1)"]


def test_handle_add_text_query_resolves_to_youtube(monkeypatch):
    client = FakeIRCClient()
    handlers = CommandHandlers(client)
    calls = []

    monkeypatch.setattr(
        handlers,
        "_resolve_youtube_query",
        lambda query: "https://www.youtube.com/watch?v=aaaaaaaaaaa",
    )

    def fake_add_to_queue(url, submitter_username, notes=None):
        calls.append((url, submitter_username, notes))
        return True, "Added to queue (position 4)", 4

    monkeypatch.setattr("quetie.twitch_bot.handlers.queue_manager.add_to_queue", fake_add_to_queue)

    handlers.handle_add("miss_brain_glitch", "daft punk one more time")

    assert calls == [
        (
            "https://www.youtube.com/watch?v=aaaaaaaaaaa",
            "miss_brain_glitch",
            "Query: daft punk one more time",
        )
    ]
    assert client.messages == [
        "@miss_brain_glitch Added to queue (position 4) (matched: https://www.youtube.com/watch?v=aaaaaaaaaaa)"
    ]


def test_handle_add_multiple_free_text_queries(monkeypatch):
    client = FakeIRCClient()
    handlers = CommandHandlers(client)
    calls = []
    resolved = {
        "songone": "https://www.youtube.com/watch?v=aaaaaaaaaaa",
        "songtwo": "https://www.youtube.com/watch?v=bbbbbbbbbbb",
    }

    monkeypatch.setattr(
        handlers,
        "_resolve_youtube_query",
        lambda query: resolved[query],
    )

    def fake_add_to_queue(url, submitter_username, notes=None):
        calls.append((url, submitter_username, notes))
        return True, f"Added to queue (position {len(calls)})", len(calls)

    monkeypatch.setattr("quetie.twitch_bot.handlers.queue_manager.add_to_queue", fake_add_to_queue)

    handlers.handle_add("miss_brain_glitch", "songone songtwo")

    assert calls == [
        ("https://www.youtube.com/watch?v=aaaaaaaaaaa", "miss_brain_glitch", "Query: songone"),
        ("https://www.youtube.com/watch?v=bbbbbbbbbbb", "miss_brain_glitch", "Query: songtwo"),
    ]
    assert client.messages == ["@miss_brain_glitch Queued 2 items at positions: 1, 2"]


def test_resolve_youtube_query_falls_back_to_duckduckgo(monkeypatch):
    client = FakeIRCClient()
    handlers = CommandHandlers(client)

    class FakeResponse:
        def __init__(self, body):
            self._body = body

        def read(self):
            return self._body.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout=6):
        url = request.full_url
        if "youtube.com/results" in url:
            return FakeResponse("no matches here")
        return FakeResponse(
            '...uddg=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3DdQw4w9WgXcQ...'
        )

    monkeypatch.setattr("quetie.twitch_bot.handlers.urllib.request.urlopen", fake_urlopen)

    resolved = handlers._resolve_youtube_query("cinderella\'s dead song")

    assert resolved == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
