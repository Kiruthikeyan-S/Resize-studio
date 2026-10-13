"""Tests for 15 fixed-size outputs and custom selected-ZIP download."""

import io
import json
import zipfile
from PIL import Image
from fastapi.testclient import TestClient

from main import app
from services.crop_engine import SIZE_PRESETS, all_selection_ids

client = TestClient(app)

EXPECTED = {
    "square_1x1": {"large": (2048, 2048), "medium": (1080, 1080), "small": (512, 512)},
    "portrait_4x5": {"large": (1600, 2000), "medium": (1080, 1350), "small": (800, 1000)},
    "portrait_3x4": {"large": (1536, 2048), "medium": (1080, 1440), "small": (768, 1024)},
    "landscape_16x9": {"large": (2560, 1440), "medium": (1920, 1080), "small": (1280, 720)},
    "landscape_5x4": {"large": (2000, 1600), "medium": (1350, 1080), "small": (1000, 800)},
}


def _jpeg(size=(1200, 800), color=(90, 140, 200)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _setup(size=(1200, 800), color=(90, 140, 200)):
    up = client.post("/api/upload", files={"file": ("p.jpg", _jpeg(size, color), "image/jpeg")})
    assert up.status_code == 200
    image_id = up.json()["image_id"]
    conv = client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop"})
    assert conv.status_code == 200
    return image_id, conv.json()


def _zip(image_id, selections, revision=None):
    body = {"image_id": image_id, "selections": selections}
    if revision is not None:
        body["revision"] = revision
    return client.post("/api/download-selected", json=body)


def test_presets_match_spec_and_15_ids():
    assert SIZE_PRESETS == EXPECTED
    assert len(all_selection_ids()) == 15


def test_convert_generates_15_variants_with_exact_sizes():
    _, data = _setup()
    total = 0
    for out in data["outputs"]:
        assert [v["size_key"] for v in out["variants"]] == ["large", "medium", "small"]
        for v in out["variants"]:
            assert (v["width"], v["height"]) == EXPECTED[out["safe_key"]][v["size_key"]]
            total += 1
    assert total == 15
    assert "file_path" not in json.dumps(data)  # server paths never exposed


def test_select_one_image_zip_has_exactly_one_image():
    image_id, data = _setup()
    res = _zip(image_id, ["square_1x1:large"], data["revision"])
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        images = [n for n in zf.namelist() if n != "manifest.json"]
        assert images == ["image_square_1x1_large.jpg"]
        assert Image.open(io.BytesIO(zf.read(images[0]))).size == (2048, 2048)


def test_select_three_images_exact_names_dimensions_and_manifest():
    image_id, data = _setup()
    sel = ["square_1x1:large", "portrait_4x5:medium", "landscape_16x9:small"]
    res = _zip(image_id, sel, data["revision"])
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        images = sorted(n for n in zf.namelist() if n != "manifest.json")
        assert images == sorted([
            "image_square_1x1_large.jpg",
            "image_portrait_4x5_medium.jpg",
            "image_landscape_16x9_small.jpg",
        ])
        assert Image.open(io.BytesIO(zf.read("image_portrait_4x5_medium.jpg"))).size == (1080, 1350)
        assert Image.open(io.BytesIO(zf.read("image_landscape_16x9_small.jpg"))).size == (1280, 720)
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["selected_count"] == 3
        assert sorted(f["filename"] for f in manifest["files"]) == images
        # no raw/original upload leaked into the archive
        assert not any(n.startswith(("raw", "working", "original")) for n in zf.namelist())


def test_select_all_15():
    image_id, data = _setup()
    res = _zip(image_id, all_selection_ids(), data["revision"])
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        images = [n for n in zf.namelist() if n != "manifest.json"]
        assert len(images) == 15 and len(set(images)) == 15
        for name in images:
            ratio, size = name[len("image_"):-len(".jpg")].rsplit("_", 1)
            assert Image.open(io.BytesIO(zf.read(name))).size == EXPECTED[ratio][size]


def test_empty_selection_rejected():
    image_id, data = _setup()
    assert _zip(image_id, [], data["revision"]).status_code == 422


def test_invalid_and_duplicate_selection_rejected():
    image_id, data = _setup()
    assert _zip(image_id, ["square_1x1:huge"], data["revision"]).status_code == 422
    assert _zip(image_id, ["nope:large"], data["revision"]).status_code == 422
    assert _zip(image_id, ["../../etc/passwd"], data["revision"]).status_code == 422
    assert _zip(image_id, ["square_1x1:large", "square_1x1:large"], data["revision"]).status_code == 422


def test_unknown_session_and_bad_id():
    assert _zip("a" * 32, ["square_1x1:large"]).status_code == 404
    assert _zip("../bad", ["square_1x1:large"]).status_code in (400, 422)


def test_missing_generated_file_gives_meaningful_error():
    import os
    from services.image_processor import get_image_session_dirs
    image_id, data = _setup()
    _, gen_dir = get_image_session_dirs(image_id)
    os.remove(os.path.join(gen_dir, "image_square_1x1_small.jpg"))
    res = _zip(image_id, ["square_1x1:small"], data["revision"])
    assert res.status_code == 404
    assert "missing" in res.json()["detail"].lower()


def test_reedit_uses_only_new_generation_and_rejects_stale_revision():
    image_id, first = _setup(size=(1200, 800), color=(10, 20, 30))
    old_rev = first["revision"]

    # Re-edit source: crop to a different region, regenerate
    up = client.post("/api/update-original", json={"image_id": image_id, "crop_box": [0, 0, 600, 400]})
    assert up.status_code == 200
    # Old outputs are invalidated until regenerated
    assert _zip(image_id, ["square_1x1:large"], old_rev).status_code == 404

    conv = client.post("/api/convert", json={"image_id": image_id, "mode": "smart_crop"})
    new = conv.json()
    assert new["revision"] > old_rev
    assert all(o["source_width"] == 600 and o["source_height"] == 400 for o in new["outputs"])

    # Stale revision refused; new revision accepted
    assert _zip(image_id, ["square_1x1:large"], old_rev).status_code == 422
    ok = _zip(image_id, ["square_1x1:large"], new["revision"])
    assert ok.status_code == 200
    with zipfile.ZipFile(io.BytesIO(ok.content)) as zf:
        assert json.loads(zf.read("manifest.json"))["generation_revision"] == new["revision"]


def test_changing_selection_does_not_regenerate_files():
    import os
    from services.image_processor import get_image_session_dirs
    image_id, data = _setup()
    _, gen_dir = get_image_session_dirs(image_id)
    target = os.path.join(gen_dir, "image_portrait_3x4_medium.jpg")
    before = os.path.getmtime(target)
    for sel in (["portrait_3x4:medium"], all_selection_ids(), ["square_1x1:small"]):
        assert _zip(image_id, sel, data["revision"]).status_code == 200
    assert os.path.getmtime(target) == before
