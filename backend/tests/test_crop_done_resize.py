"""Regression tests: a confirmed crop is the only input to safe-fit exports.

Copy to backend/tests/test_crop_done_resize.py and run from backend: pytest -q tests/test_crop_done_resize.py
"""
import io
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_done_crop_is_only_source_and_default_resize_is_safe_fit():
    # Raw outer region is red; the approved inner square is solid green.
    # If the server mistakenly goes back to the raw original, red will appear.
    source = Image.new("RGB", (600, 400), (255, 0, 0))
    ImageDraw.Draw(source).rectangle([150, 50, 449, 349], fill=(0, 180, 0))
    buff = io.BytesIO()
    source.save(buff, format="PNG")

    up = client.post('/api/upload', files={'file': ('original.png', buff.getvalue(), 'image/png')})
    assert up.status_code == 200, up.text
    image_id = up.json()['image_id']

    done = client.post('/api/update-original', json={
        'image_id': image_id, 'crop_box': [150, 50, 450, 350]
    })
    assert done.status_code == 200, done.text
    assert done.json()['is_cropped_master'] is True
    assert (done.json()['width'], done.json()['height']) == (300, 300)

    approved = client.get(f'/api/original/{image_id}')
    assert approved.status_code == 200
    with Image.open(io.BytesIO(approved.content)) as img:
        assert img.size == (300, 300)
        assert img.getpixel((150, 150)) == (0, 180, 0)

    # No explicit mode: the resize endpoint MUST default to non-AI safe-fit.
    conv = client.post('/api/convert', json={'image_id': image_id})
    assert conv.status_code == 200, conv.text
    info = conv.json()
    assert info['mode'] == 'safe_fit'
    assert len(info['outputs']) == 5
    assert sum(len(out['variants']) for out in info['outputs']) == 15
    for out in info['outputs']:
        assert out['source_width'] == 300
        assert out['source_height'] == 300
        assert out['mode'] == 'safe_fit'
        for variant in out['variants']:
            res = client.get(
                f"/api/download/{image_id}/{out['safe_key']}?size={variant['size_key']}"
            )
            assert res.status_code == 200
            with Image.open(io.BytesIO(res.content)) as img:
                assert img.size == (variant['width'], variant['height'])
                px = img.convert('RGB').getpixel((img.width // 2, img.height // 2))
                assert px[1] > 120 and px[0] < 50, (
                    f"Unexpected source content in {out['safe_key']} {variant['size_key']}: {px}"
                )
