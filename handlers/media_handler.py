from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
from types import TracebackType
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MEDIA_DIR = ROOT / "media"

VIDEO_EXTENSIONS = frozenset(
    {
        ".mp4",
        ".mkv",
        ".mov",
        ".avi",
        ".webm",
        ".3gp",
        ".m4v",
        ".flv",
        ".wmv",
        ".mpeg",
        ".mpg",
    }
)


def _is_video_path(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


@dataclass
class _Channel:
    path: Path
    process: subprocess.Popen[bytes] | None = None
    video: Any | None = None
    thread: threading.Thread | None = None
    stop_event: threading.Event | None = None
    paused: bool = False

    @property
    def is_video(self) -> bool:
        return _is_video_path(self.path)


class MediaHandler:
    """
    Handles media playback and control.

    Each named channel maps to one media file. Audio uses system players
    (mpg123 or aplay) in a subprocess with SIGSTOP/SIGCONT for pause.
    Video uses pyvidplayer2 in a background thread with a Pygame window,
    looping when the file ends.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._channels: dict[str, _Channel] = {}

    def add_channel(
        self,
        channel_name: str,
        media_file: str,
        media_dir: str | Path = DEFAULT_MEDIA_DIR,
    ) -> None:
        path = Path(media_dir) / media_file
        if not path.is_file():
            raise FileNotFoundError(f"Media file not found: {path}")

        with self._lock:
            existing = self._channels.get(channel_name)
            if existing is not None:
                self._stop_playback(existing)
            self._channels[channel_name] = _Channel(path=path)
            kind = "video" if _is_video_path(path) else "audio"
            logger.info(
                f"MediaHandler: Registered {kind} channel {channel_name} -> {path}"
            )

    def close_channel(self, channel_name: str) -> None:
        with self._lock:
            channel = self._channels.pop(channel_name, None)
        if channel is not None:
            self._stop_playback(channel)
            logger.info(f"MediaHandler: Closed media channel {channel_name}")

    def play_channel(self, channel_name: str) -> None:
        with self._lock:
            channel = self._require_channel(channel_name)

        if channel.is_video:
            self._play_video(channel_name, channel)
        else:
            self._play_audio(channel_name, channel)

    def pause_channel(self, channel_name: str) -> None:
        with self._lock:
            channel = self._require_channel(channel_name)
            if channel.paused:
                return

            if channel.is_video:
                video = channel.video
                if video is None or channel.thread is None or not channel.thread.is_alive():
                    return
                video.pause()
                channel.paused = True
                logger.info(f"MediaHandler: Paused media channel {channel_name}")
                return

            process = channel.process
            if process is None or process.poll() is not None:
                return
            os.kill(process.pid, signal.SIGSTOP)
            channel.paused = True
            logger.info(f"MediaHandler: Paused media channel {channel_name}")

    def close(self) -> None:
        with self._lock:
            channels = list(self._channels.values())
            self._channels.clear()
        for channel in channels:
            self._stop_playback(channel)

    def _require_channel(self, channel_name: str) -> _Channel:
        try:
            return self._channels[channel_name]
        except KeyError as exc:
            raise KeyError(f"MediaHandler: Unknown media channel {channel_name}") from exc

    def _play_audio(self, channel_name: str, channel: _Channel) -> None:
        with self._lock:
            process = channel.process
            if process is not None and process.poll() is None:
                if channel.paused:
                    os.kill(process.pid, signal.SIGCONT)
                    channel.paused = False
                    logger.info(f"MediaHandler: Resumed media channel {channel_name}")
                return
            channel.paused = False

        self._start_audio_process(channel)
        logger.info(f"MediaHandler: Playing media channel {channel_name}")

    def _play_video(self, channel_name: str, channel: _Channel) -> None:
        with self._lock:
            thread = channel.thread
            if thread is not None and thread.is_alive():
                if channel.paused and channel.video is not None:
                    channel.video.resume()
                    channel.paused = False
                    logger.info(f"MediaHandler: Resumed media channel {channel_name}")
                return
            channel.paused = False
            stop_event = threading.Event()
            channel.stop_event = stop_event
            thread = threading.Thread(
                target=self._run_video_loop,
                args=(channel_name, channel, stop_event),
                name=f"media-{channel_name}",
                daemon=True,
            )
            channel.thread = thread
            thread.start()

        logger.info(f"MediaHandler: Playing media channel {channel_name}")

    def _run_video_loop(
        self,
        channel_name: str,
        channel: _Channel,
        stop_event: threading.Event,
    ) -> None:
        try:
            import pygame
            from pyvidplayer2 import Video
        except ImportError as exc:
            logger.error(f"MediaHandler: pyvidplayer2 unavailable for {channel_name}: {exc}")
            return

        vid: Any | None = None
        try:
            vid = Video(str(channel.path))
            with self._lock:
                channel.video = vid

            if not pygame.get_init():
                pygame.init()
            if not pygame.display.get_init():
                pygame.display.init()

            win = pygame.display.set_mode(vid.current_size)
            pygame.display.set_caption(f"{channel_name}: {vid.name}")
            vid.play()

            clock = pygame.time.Clock()
            while not stop_event.is_set():
                if not vid.active:
                    vid.restart()
                    vid.play()

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        stop_event.set()
                        break

                with self._lock:
                    paused = channel.paused

                if paused:
                    if not vid.paused:
                        vid.pause()
                elif vid.paused:
                    vid.resume()
                elif vid.draw(win, (0, 0), force_draw=False):
                    pygame.display.update()

                clock.tick(60)
        except Exception:
            logger.exception(f"MediaHandler: Video playback failed for {channel_name}")
        finally:
            if vid is not None:
                try:
                    vid.close()
                except Exception:
                    logger.exception(
                        f"MediaHandler: Error closing video for {channel_name}"
                    )
            with self._lock:
                channel.video = None
                channel.thread = None
                channel.stop_event = None
                channel.paused = False

    def _start_audio_process(self, channel: _Channel) -> None:
        self._stop_audio_process(channel)
        cmd = self._audio_player_command(channel.path)
        channel.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        channel.paused = False

    def _stop_playback(self, channel: _Channel) -> None:
        if channel.is_video:
            self._stop_video(channel)
        else:
            self._stop_audio_process(channel)

    def _stop_video(self, channel: _Channel) -> None:
        stop_event = channel.stop_event
        if stop_event is not None:
            stop_event.set()

        video = channel.video
        if video is not None:
            try:
                video.stop()
            except Exception:
                pass

        thread = channel.thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5)

        if video is not None:
            try:
                video.close()
            except Exception:
                pass

        channel.video = None
        channel.thread = None
        channel.stop_event = None
        channel.paused = False

    def _stop_audio_process(self, channel: _Channel) -> None:
        process = channel.process
        if process is None:
            channel.paused = False
            return
        if process.poll() is None:
            if channel.paused:
                try:
                    os.kill(process.pid, signal.SIGCONT)
                except ProcessLookupError:
                    pass
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        channel.process = None
        channel.paused = False

    def _audio_player_command(self, path: Path) -> list[str]:
        ext = path.suffix.lower()
        mpg123 = shutil.which("mpg123")
        if mpg123 and ext in {".mp3", ".mp2"}:
            return [mpg123, "-q", "--loop", str(path)]

        aplay = shutil.which("aplay")
        if aplay and ext in {".wav", ".wave"}:
            return [aplay, str(path)]

        raise RuntimeError(
            f"No suitable audio player found for {path} (extension {ext!r})"
        )

    def __enter__(self) -> MediaHandler:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> None:
        for channel_name in list(self._channels.keys()):
            self.close_channel(channel_name)
