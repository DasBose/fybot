import signal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from handlers.media_handler import MediaHandler


@pytest.fixture
def media_dir(tmp_path: Path) -> Path:
    media_file = tmp_path / "track.mp3"
    media_file.write_bytes(b"fake")
    return tmp_path


@pytest.fixture
def video_dir(tmp_path: Path) -> Path:
    media_file = tmp_path / "clip.mp4"
    media_file.write_bytes(b"fake")
    return tmp_path


@pytest.fixture
def handler() -> MediaHandler:
    return MediaHandler()


def test_add_channel_registers_file(handler: MediaHandler, media_dir: Path) -> None:
    handler.add_channel("ambient", "track.mp3", str(media_dir))

    with pytest.raises(KeyError, match="Unknown media channel"):
        handler.pause_channel("missing")


def test_add_channel_missing_file_raises(handler: MediaHandler, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        handler.add_channel("ambient", "nope.mp3", str(tmp_path))


@patch("handlers.media_handler.shutil.which", return_value="/usr/bin/mpg123")
@patch("handlers.media_handler.subprocess.Popen")
def test_play_channel_starts_player(
    popen: MagicMock,
    _which: MagicMock,
    handler: MediaHandler,
    media_dir: Path,
) -> None:
    process = MagicMock()
    process.poll.return_value = None
    process.pid = 4242
    popen.return_value = process

    handler.add_channel("ambient", "track.mp3", str(media_dir))
    handler.play_channel("ambient")

    popen.assert_called_once()
    assert popen.call_args.args[0] == [
        "/usr/bin/mpg123",
        "-q",
        "--loop",
        str(media_dir / "track.mp3"),
    ]


@patch("handlers.media_handler.shutil.which", return_value="/usr/bin/mpg123")
@patch("handlers.media_handler.subprocess.Popen")
@patch("handlers.media_handler.os.kill")
def test_pause_and_resume_use_signals(
    kill: MagicMock,
    popen: MagicMock,
    _which: MagicMock,
    handler: MediaHandler,
    media_dir: Path,
) -> None:
    process = MagicMock()
    process.poll.return_value = None
    process.pid = 4242
    popen.return_value = process

    handler.add_channel("ambient", "track.mp3", str(media_dir))
    handler.play_channel("ambient")
    handler.pause_channel("ambient")
    handler.play_channel("ambient")

    kill.assert_any_call(4242, signal.SIGSTOP)
    kill.assert_any_call(4242, signal.SIGCONT)


@patch("handlers.media_handler.shutil.which", return_value="/usr/bin/mpg123")
@patch("handlers.media_handler.subprocess.Popen")
def test_close_channel_stops_player(
    popen: MagicMock,
    _which: MagicMock,
    handler: MediaHandler,
    media_dir: Path,
) -> None:
    process = MagicMock()
    process.poll.return_value = None
    process.pid = 4242
    popen.return_value = process

    handler.add_channel("ambient", "track.mp3", str(media_dir))
    handler.play_channel("ambient")
    handler.close_channel("ambient")

    process.terminate.assert_called_once()
    with pytest.raises(KeyError, match="Unknown media channel"):
        handler.play_channel("ambient")


@patch("handlers.media_handler.shutil.which", return_value="/usr/bin/mpg123")
def test_audio_unknown_extension_raises(
    _which: MagicMock,
    handler: MediaHandler,
    tmp_path: Path,
) -> None:
    audio = tmp_path / "tone.ogg"
    audio.write_bytes(b"fake")
    handler.add_channel("ambient", "tone.ogg", str(tmp_path))

    with pytest.raises(RuntimeError, match="No suitable audio player"):
        handler.play_channel("ambient")


@patch("handlers.media_handler.threading.Thread")
def test_play_video_starts_background_thread(
    thread_cls: MagicMock,
    handler: MediaHandler,
    video_dir: Path,
) -> None:
    thread = MagicMock()
    thread.is_alive.return_value = False
    thread_cls.return_value = thread

    handler.add_channel("screen", "clip.mp4", str(video_dir))
    handler.play_channel("screen")

    thread_cls.assert_called_once()
    assert thread_cls.call_args.kwargs["name"] == "media-screen"
    thread.start.assert_called_once()
    assert "pyvidplayer2" not in str(thread_cls.call_args.kwargs)


@patch("handlers.media_handler.threading.Thread")
def test_play_video_does_not_use_subprocess(
    thread_cls: MagicMock,
    handler: MediaHandler,
    video_dir: Path,
) -> None:
    thread_cls.return_value = MagicMock(is_alive=MagicMock(return_value=False))

    with patch("handlers.media_handler.subprocess.Popen") as popen:
        handler.add_channel("screen", "clip.mp4", str(video_dir))
        handler.play_channel("screen")

    popen.assert_not_called()


def test_pause_video_calls_pyvidplayer_pause(handler: MediaHandler, video_dir: Path) -> None:
    video = MagicMock()
    video.paused = False
    thread = MagicMock()
    thread.is_alive.return_value = True

    handler.add_channel("screen", "clip.mp4", str(video_dir))
    channel = handler._channels["screen"]
    channel.video = video
    channel.thread = thread

    handler.pause_channel("screen")

    video.pause.assert_called_once()
    assert channel.paused is True


def test_resume_video_calls_pyvidplayer_resume(handler: MediaHandler, video_dir: Path) -> None:
    video = MagicMock()
    video.paused = True
    thread = MagicMock()
    thread.is_alive.return_value = True

    handler.add_channel("screen", "clip.mp4", str(video_dir))
    channel = handler._channels["screen"]
    channel.video = video
    channel.thread = thread
    channel.paused = True

    handler.play_channel("screen")

    video.resume.assert_called_once()
    assert channel.paused is False
