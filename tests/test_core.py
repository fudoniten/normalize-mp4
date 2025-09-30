from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from normalize_mp4 import Context, copy_or_move, generate_new_path, get_video_metadata, process_videos


@pytest.fixture
def ctx() -> Context:
    return Context(ffprobe_path=Path("/usr/bin/ffprobe"))


@pytest.fixture
def make_probe(monkeypatch):
    import ffmpeg

    def _install(mapping):
        def fake_probe(path, cmd=None):  # noqa: ARG001
            probe = mapping.get(Path(path).name)
            if probe is None:
                raise ffmpeg.Error("ffprobe", b"", b"file not found in mapping")
            return probe

        monkeypatch.setattr(ffmpeg, "probe", fake_probe)

    return _install


def fake_probe_dict(
    duration: float | None = None,
    vstream_duration: float | None = None,
    show: str | None = None,
    title: str | None = None,
    creation_time: str | None = None,
):
    fmt_tags: dict[str, str] = {}
    if show:
        fmt_tags["show"] = show
    if title:
        fmt_tags["title"] = title
    if creation_time:
        fmt_tags["creation_time"] = creation_time

    fmt: dict[str, object] = {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "tags": fmt_tags}
    if duration is not None:
        fmt["duration"] = str(duration)

    streams = [{"codec_type": "video"}]
    if vstream_duration is not None:
        streams[0]["duration"] = str(vstream_duration)

    return {"format": fmt, "streams": streams}


@pytest.mark.parametrize(
    "ctime",
    [
        "2023-03-01T12:34:56.789Z",
        "2023-03-01T12:34:56Z",
        "2023-03-01 12:34:56",
        "2023-03-01T12:34:56.789",
    ],
)
def test_get_video_metadata_creation_formats(tmp_path, ctx, make_probe, ctime):
    file_path = tmp_path / "clip.mp4"
    file_path.write_bytes(b"dummy")

    make_probe({
        "clip.mp4": fake_probe_dict(duration=12.5, show="My Show", title="Ep 1", creation_time=ctime)
    })

    meta = get_video_metadata(ctx, file_path)
    assert meta is not None
    assert meta["video_length"] == pytest.approx(12.5)
    assert meta["show_name"] == "My Show"
    assert meta["episode_name"] == "Ep 1"
    assert meta["year"] == 2023
    assert meta["date_str"].startswith("2023-03-01")
    assert meta["ext"] == ".mp4"


def test_get_video_metadata_uses_format_then_stream_duration(tmp_path, ctx, make_probe):
    f1 = tmp_path / "has_format_dur.mp4"
    f2 = tmp_path / "has_stream_dur.mp4"
    f1.write_bytes(b"x")
    f2.write_bytes(b"x")

    make_probe({
        "has_format_dur.mp4": fake_probe_dict(duration=100.0, vstream_duration=None, title="A"),
        "has_stream_dur.mp4": fake_probe_dict(duration=None, vstream_duration=55.0, title="B"),
    })

    meta1 = get_video_metadata(ctx, f1)
    meta2 = get_video_metadata(ctx, f2)
    assert meta1["video_length"] == pytest.approx(100.0)
    assert meta2["video_length"] == pytest.approx(55.0)


def test_get_video_metadata_falls_back_to_filename_and_mtime(tmp_path, ctx, make_probe):
    file_path = tmp_path / "Fallback Name.mkv"
    file_path.write_bytes(b"x")

    make_probe({"Fallback Name.mkv": fake_probe_dict(duration=None, vstream_duration=None)})
    assert get_video_metadata(ctx, file_path) is None

    make_probe({"Fallback Name.mkv": fake_probe_dict(duration=None, vstream_duration=42.0)})
    meta = get_video_metadata(ctx, file_path)
    assert meta["episode_name"] == "Fallback Name"
    assert meta["show_name"] == "Unknown Show"
    assert meta["year"] == datetime.fromtimestamp(file_path.stat().st_mtime).year
    assert meta["ext"] == ".mkv"


def test_generate_new_path_sanitizes(tmp_path):
    target = tmp_path / "content"
    new_path = generate_new_path(
        target_dir=target,
        show_name="My: Show/Bad*Name?",
        episode_name="Title: <Bad>|Name",
        year=2024,
        date_str="2024-01-02",
        ext=".mp4",
    )
    assert new_path.suffix == ".mp4"
    assert (tmp_path / "content") in new_path.parents


def test_copy_or_move_collision_suffix(tmp_path):
    src = tmp_path / "source.mp4"
    dst_dir = tmp_path / "out"
    dst = dst_dir / "file.mp4"

    dst_dir.mkdir()
    src.write_bytes(b"data")
    dst.write_bytes(b"existing")

    ok = copy_or_move(src, dst, move=False, overwrite=False)
    assert ok
    created = sorted(dst_dir.glob("file*.mp4"))
    assert len(created) == 2
    assert (dst_dir / "file.mp4").exists()
    assert any(p.name.startswith("file [") for p in created if p.name != "file.mp4")


def test_copy_or_move_move_and_overwrite(tmp_path):
    src = tmp_path / "x.mp4"
    dst = tmp_path / "y.mp4"
    src.write_bytes(b"abc")
    dst.write_bytes(b"old")

    ok = copy_or_move(src, dst, move=True, overwrite=True)
    assert ok
    assert dst.read_bytes() == b"abc"
    assert not src.exists()


def test_process_videos_routes_long_vs_short(tmp_path, ctx, make_probe, monkeypatch):
    basedir = tmp_path / "scan"
    content_dir = tmp_path / "content"
    filler_dir = tmp_path / "filler"
    basedir.mkdir()
    (basedir / "a").mkdir()

    long_file = basedir / "long.mp4"
    short_file = basedir / "short.mp4"
    long_file.write_bytes(b"x")
    short_file.write_bytes(b"x")

    make_probe({
        "long.mp4": fake_probe_dict(duration=601.0, title="Long Episode", show="Show"),
        "short.mp4": fake_probe_dict(duration=300.0, title="Short Episode", show="Show"),
    })

    def fake_walk(path):
        yield str(path), ["long.mp4", "short.mp4"]

    monkeypatch.setattr("normalize_mp4.core._walk_videos", fake_walk)

    process_videos(
        basedir=basedir,
        content_dir=content_dir,
        filler_dir=filler_dir,
        filler_threshold=600,
        default_show_name="Default",
        ctx=ctx,
        move=False,
        overwrite=False,
        dry_run=False,
    )

    assert any(content_dir.rglob("*Long Episode*"))
    assert any(filler_dir.rglob("*Short Episode*"))
