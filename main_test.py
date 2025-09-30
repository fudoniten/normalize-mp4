# test_video_sorter.py
import io
import os
from pathlib import Path
import shutil
import types
import pytest

# 👇 Adjust this import to your actual module filename
from video_sorter import (
    Context,
    get_video_metadata,
    generate_new_path,
    copy_or_move,
    process_videos,
)

# ------------------------
# Fixtures & test helpers
# ------------------------

@pytest.fixture
def ctx():
    # The path value isn't used because we monkeypatch ffmpeg.probe,
    # but Context requires it.
    return Context(ffprobe_path=Path("/usr/bin/ffprobe"))

@pytest.fixture
def make_probe(monkeypatch):
    """
    Helper to patch ffmpeg.probe with a controllable function.
    Usage:
        make_probe(setup=dict(file_name -> probe_dict))
    """
    import ffmpeg

    def _install(mapping):
        def fake_probe(path, cmd=None):
            # Path can be str or Path
            p = Path(path)
            probe = mapping.get(p.name)
            if probe is None:
                raise ffmpeg.Error("ffprobe", b"", b"file not found in mapping")
            return probe
        monkeypatch.setattr(ffmpeg, "probe", fake_probe)
    return _install

def fake_probe_dict(
    duration=None,
    vstream_duration=None,
    show=None,
    title=None,
    creation_time=None,
):
    fmt_tags = {}
    if show:
        fmt_tags["show"] = show
    if title:
        fmt_tags["title"] = title
    if creation_time:
        fmt_tags["creation_time"] = creation_time

    fmt = {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "tags": fmt_tags}
    if duration is not None:
        fmt["duration"] = str(duration)

    streams = [{"codec_type": "video"}]
    if vstream_duration is not None:
        streams[0]["duration"] = str(vstream_duration)

    return {"format": fmt, "streams": streams}

# ------------------------
# Tests for get_video_metadata
# ------------------------

@pytest.mark.parametrize(
    "ctime",
    [
        "2023-03-01T12:34:56.789Z",
        "2023-03-01T12:34:56Z",
        "2023-03-01 12:34:56",
        "2023-03-01T12:34:56.789",  # no Z
    ],
)
def test_get_video_metadata_creation_formats(tmp_path, ctx, make_probe, ctime):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"dummy")

    make_probe({
        "clip.mp4": fake_probe_dict(duration=12.5, show="My Show", title="Ep 1", creation_time=ctime)
    })

    meta = get_video_metadata(ctx, f)
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

    m1 = get_video_metadata(ctx, f1)
    m2 = get_video_metadata(ctx, f2)
    assert m1["video_length"] == pytest.approx(100.0)
    assert m2["video_length"] == pytest.approx(55.0)

def test_get_video_metadata_falls_back_to_filename_and_mtime(tmp_path, ctx, make_probe, monkeypatch):
    f = tmp_path / "Fallback Name.mkv"
    f.write_bytes(b"x")

    # No duration -> expect error/None
    make_probe({"Fallback Name.mkv": fake_probe_dict(duration=None, vstream_duration=None)})
    assert get_video_metadata(ctx, f) is None

    # Provide stream duration; no show/title/creation_time -> defaults
    make_probe({"Fallback Name.mkv": fake_probe_dict(duration=None, vstream_duration=42.0)})
    meta = get_video_metadata(ctx, f)
    assert meta["episode_name"] == "Fallback Name"
    assert meta["show_name"] == "Unknown Show"
    assert meta["year"] == datetime_from_mtime_year(f)
    assert meta["ext"] == ".mkv"

def datetime_from_mtime_year(p: Path) -> int:
    return int(Path(p).stat().st_mtime_ns // 1_000_000_000 and
               __import__("datetime").datetime.fromtimestamp(p.stat().st_mtime).year)

# ------------------------
# Tests for path generation & sanitization
# ------------------------

def test_generate_new_path_sanitizes(tmp_path):
    target = tmp_path / "content"
    newp = generate_new_path(
        target_dir=target,
        show_name='My: Show/Bad*Name?',
        episode_name='Title: <Bad>|Name',
        year=2024,
        date_str="2024-01-02",
        ext=".mp4",
    )
    # Should be under a sanitized subdir and filename
    assert newp.suffix == ".mp4"
    assert (tmp_path / "content") in newp.parents
    assert "My" in newp.as_posix()  # rough check the path was built

# ------------------------
# Tests for copy_or_move (filesystem behavior)
# ------------------------

def test_copy_or_move_collision_suffix(tmp_path):
    src = tmp_path / "source.mp4"
    dst_dir = tmp_path / "out"
    dst = dst_dir / "file.mp4"

    dst_dir.mkdir()
    src.write_bytes(b"data")
    dst.write_bytes(b"existing")

    ok = copy_or_move(src, dst, move=False, overwrite=False)
    assert ok
    # Should have created file like file [1].mp4
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

# ------------------------
# Tests for process_videos routing & dry-run
# ------------------------

def test_process_videos_routes_long_vs_short(tmp_path, ctx, make_probe):
    """
    Create two files; one 'long' (> threshold) and one 'short' (<= threshold),
    and verify they are planned/copied to content_dir and filler_dir respectively.
    """
    basedir = tmp_path / "scan"
    content_dir = tmp_path / "content"
    filler_dir = tmp_path / "filler"
    basedir.mkdir()
    (basedir / "long.mp4").write_bytes(b"L")
    (basedir / "short.mkv").write_bytes(b"S")

    make_probe({
        "long.mp4": fake_probe_dict(duration=1000, show="LongShow", title="Long Ep", creation_time="2024-05-01T00:00:00Z"),
        "short.mkv": fake_probe_dict(duration=120, show="ShortShow", title="Short Ep", creation_time="2024-05-02T00:00:00Z"),
    })

    # First dry-run (no files created)
    process_videos(
        basedir=basedir,
        content_dir=content_dir,
        filler_dir=filler_dir,
        filler_threshold=600,
        default_show_name="DefaultShow",
        ctx=ctx,
        move=False,
        overwrite=False,
        dry_run=True,
    )
    assert not any(content_dir.rglob("*"))
    assert not any(filler_dir.rglob("*"))

    # Now actually copy
    process_videos(
        basedir=basedir,
        content_dir=content_dir,
        filler_dir=filler_dir,
        filler_threshold=600,
        default_show_name="DefaultShow",
        ctx=ctx,
        move=False,
        overwrite=False,
        dry_run=False,
    )

    # Verify long goes to content, short to filler; and extension preserved
    long_files = list(content_dir.rglob("*.mp4"))
    short_files = list(filler_dir.rglob("*.mkv"))
    assert len(long_files) == 1
    assert len(short_files) == 1
    assert "LongShow" in long_files[0].as_posix()
    assert "ShortShow" in short_files[0].as_posix()

def test_process_videos_uses_default_show_when_unknown(tmp_path, ctx, make_probe):
    basedir = tmp_path / "scan"
    content_dir = tmp_path / "content"
    filler_dir = tmp_path / "filler"
    basedir.mkdir()
    (basedir / "file.mp4").write_bytes(b"x")

    # No 'show' tag
    make_probe({"file.mp4": fake_probe_dict(duration=700, show=None, title="Title")})

    process_videos(
        basedir=basedir,
        content_dir=content_dir,
        filler_dir=filler_dir,
        filler_threshold=600,
        default_show_name="Fallback Show",
        ctx=ctx,
        move=False,
        overwrite=False,
        dry_run=False,
    )
    out = list(content_dir.rglob("*"))
    # Expect path contains Fallback Show
    assert any("Fallback Show" in p.as_posix() for p in out)
