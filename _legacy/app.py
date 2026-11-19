"""Aplikasi web deteksi karya seni AI vs Human (Flask + Swin Transformer + Grad-CAM).

Jalankan (venv aktif, dari folder art-detector):
    python app.py
Lalu buka http://127.0.0.1:5000
"""
import base64
import io
import threading
from pathlib import Path

import cv2
import numpy as np
import timm
import torch
from flask import Flask, jsonify, render_template, request
from PIL import Image
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from torchvision import transforms as T

from config import (ARCH, CLASSES, JPEG_QUALITY, LABELS, MATCH_TRAINING,
                    MEAN, MODEL_FILE, STD)

BASE = Path(__file__).parent
ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # maks 10 MB


def load_model():
    ck = torch.load(BASE / MODEL_FILE, map_location="cpu")
    sd = ck
    if isinstance(ck, dict):
        for k in ("model", "state_dict", "model_state_dict"):
            if k in ck:
                sd = ck[k]
                break
    m = timm.create_model(ARCH, pretrained=False, num_classes=2)
    m.load_state_dict(sd)
    m.eval()
    return m


def reshape_transform(t):
    # Swin: (B, N, C) atau (B, H, W, C) -> (B, C, H, W)
    if t.ndim == 3:
        n = int(t.shape[1] ** 0.5)
        t = t.reshape(t.size(0), n, n, t.size(2))
    return t.permute(0, 3, 1, 2)


model = load_model()
tf = T.Compose([T.Resize((224, 224)), T.ToTensor(), T.Normalize(MEAN, STD)])
cam = GradCAM(model=model,
              target_layers=[model.layers[-1].blocks[-1].norm1],
              reshape_transform=reshape_transform)
cam_lock = threading.Lock()  # Grad-CAM memakai hook, satu permintaan sekali jalan

print(f"Model: {MODEL_FILE} | urutan kelas: {CLASSES}")


def match_training(img):
    """Samakan dengan data latih: 256x256 JPEG."""
    img = img.resize((256, 256), Image.BICUBIC)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def read_image():
    """Baca gambar dari form. Mengembalikan (gambar, None) atau (None, respons_error)."""
    f = request.files.get("image")
    if f is None or f.filename == "":
        return None, (jsonify(error="Pilih gambar dulu."), 400)
    if Path(f.filename).suffix.lower() not in ALLOWED:
        return None, (jsonify(error="Format harus JPG, PNG, atau WEBP."), 400)
    try:
        img = Image.open(f.stream).convert("RGB")
    except Exception:
        return None, (jsonify(error="File bukan gambar yang valid."), 400)
    if MATCH_TRAINING:
        img = match_training(img)
    return img, None


def summarize(prob):
    """prob: tensor probabilitas urut CLASSES. Semua pemetaan label lewat sini."""
    p = {c: float(prob[i]) for i, c in enumerate(CLASSES)}
    pred = int(prob.argmax())
    return pred, dict(
        label=LABELS[CLASSES[pred]],
        confidence=round(float(prob[pred]) * 100, 1),
        human=round(p["human"] * 100, 1),
        ai=round(p["ai"] * 100, 1),
    )


def to_b64(arr):
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    img, err = read_image()
    if err:
        return err
    with torch.no_grad():
        prob = model(tf(img).unsqueeze(0)).softmax(1)[0]
    _, out = summarize(prob)
    return jsonify(**out)


@app.route("/explain", methods=["POST"])
def explain():
    img, err = read_image()
    if err:
        return err
    x = tf(img).unsqueeze(0)
    with cam_lock:
        with torch.no_grad():
            prob = model(x).softmax(1)[0]
        pred, out = summarize(prob)
        heat = cam(input_tensor=x, targets=[ClassifierOutputTarget(pred)])[0]

    img224 = np.asarray(img.resize((224, 224)))
    overlay = show_cam_on_image(img224.astype(np.float32) / 255.0, heat, use_rgb=True)
    heat_rgb = cv2.cvtColor(cv2.applyColorMap(np.uint8(255 * heat), cv2.COLORMAP_JET),
                            cv2.COLOR_BGR2RGB)
    return jsonify(
        label=out["label"],
        confidence=out["confidence"],
        original=to_b64(img224),
        heatmap=to_b64(heat_rgb),
        overlay=to_b64(overlay),
    )


@app.errorhandler(413)
def too_large(_):
    return jsonify(error="Ukuran file maksimal 10 MB."), 413


if __name__ == "__main__":
    app.run(debug=False)
