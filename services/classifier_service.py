"""Layanan klasifikasi citra Art_ku (sesuai Class Diagram).

Refactor dari purwarupa `_legacy/app.py` + `_legacy/config.py`:
- arsitektur  : Swin-B (`swin_base_patch4_window7_224`, varian ms_in22k_ft_in1k), num_classes=2
- bobot       : models/B_no_aug_seed42.pt (dict "model"/"state_dict"/"model_state_dict" atau state_dict)
- urutan kelas: CLASSES = ["human", "ai"]  ->  indeks 0 = HUMAN_ART, indeks 1 = AI_ART
- preprocessing: (MATCH_TRAINING) resize 256 bicubic + JPEG q90, lalu Resize 224 + ToTensor + Normalize ImageNet
- Grad-CAM    : target layer model.layers[-1].blocks[-1].norm1 + reshape_transform Swin
"""
from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import List, Optional

import numpy as np
import torch
import timm
from PIL import Image
from torchvision import transforms as T

from models.entities import Label, PredictionResult

# Tipe alias sesuai Class Diagram
Tensor = torch.Tensor
Heatmap = np.ndarray  # peta aktivasi 2D (224x224) bernilai 0..1

# ---------------------------------------------------------------------------
# Konfigurasi (persis _legacy/config.py)
# ---------------------------------------------------------------------------
ARCH = "swin_base_patch4_window7_224"   # timm tag pretrained: .ms_in22k_ft_in1k
MODEL_FILE = Path(__file__).resolve().parent.parent / "models" / "B_no_aug_seed42.pt"
CLASSES = ["human", "ai"]                # urutan output model (hasil cek_urutan.py)
LABEL_DARI_KELAS = {"human": Label.HUMAN_ART, "ai": Label.AI_ART}
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)
MATCH_TRAINING = True                    # meniru data latih: resize 256 lalu JPEG, baru 224
JPEG_QUALITY = 90


def reshape_transform(t):
    """Swin: (B, N, C) atau (B, H, W, C) -> (B, C, H, W). Persis purwarupa lama."""
    if t.ndim == 3:
        n = int(t.shape[1] ** 0.5)
        t = t.reshape(t.size(0), n, n, t.size(2))
    return t.permute(0, 3, 1, 2)


# ---------------------------------------------------------------------------
# Preprocessor
# ---------------------------------------------------------------------------
class Preprocessor:
    """-imageSize: int = 224 | -mean: List | -std: List | +transformasi(image): Tensor"""

    def __init__(self, imageSize: int = 224, mean: List[float] = None, std: List[float] = None):
        self.imageSize = imageSize
        self.mean = list(mean or MEAN)
        self.std = list(std or STD)
        self._tf = T.Compose([
            T.Resize((self.imageSize, self.imageSize)),
            T.ToTensor(),
            T.Normalize(self.mean, self.std),
        ])

    @staticmethod
    def samakanDataLatih(image: Image.Image) -> Image.Image:
        """Samakan dengan data latih: 256x256 JPEG (match_training purwarupa)."""
        img = image.convert("RGB").resize((256, 256), Image.BICUBIC)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=JPEG_QUALITY)
        buf.seek(0)
        return Image.open(buf).convert("RGB")

    def transformasi(self, image: Image.Image) -> Tensor:
        """Resize 224x224 + normalisasi ImageNet -> tensor (1, 3, 224, 224)."""
        img = image.convert("RGB")
        if MATCH_TRAINING:
            img = self.samakanDataLatih(img)
        return self._tf(img).unsqueeze(0)


# ---------------------------------------------------------------------------
# SwinClassifier
# ---------------------------------------------------------------------------
class SwinClassifier:
    """-model: SwinTransformer | -device: String | -classNames: List
    +muatBobot(): void | +prediksi(image): PredictionResult"""

    def __init__(self, preprocessor: Preprocessor, modelFile: Path = MODEL_FILE,
                 device: Optional[str] = None):
        self.preprocessor = preprocessor
        self.modelFile = Path(modelFile)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.classNames: List[Label] = [LABEL_DARI_KELAS[c] for c in CLASSES]
        self.model = None
        self.lock = threading.Lock()  # model & hook Grad-CAM dipakai bergantian

    def muatBobot(self) -> None:
        ck = torch.load(self.modelFile, map_location="cpu")
        sd = ck
        if isinstance(ck, dict):
            for k in ("model", "state_dict", "model_state_dict"):
                if k in ck:
                    sd = ck[k]
                    break
        m = timm.create_model(ARCH, pretrained=False, num_classes=len(CLASSES))
        m.load_state_dict(sd)
        m.eval()
        self.model = m.to(self.device)

    def _pastikanTermuat(self) -> None:
        if self.model is None:
            self.muatBobot()

    def prediksi(self, image: Image.Image) -> PredictionResult:
        """prediksi(image) -> transformasi(image) -> tensor -> label, confidence, probHuman, probAI."""
        self._pastikanTermuat()
        x = self.preprocessor.transformasi(image).to(self.device)
        with self.lock, torch.no_grad():
            prob = self.model(x).softmax(1)[0].cpu()
        idx = int(prob.argmax())
        p = {self.classNames[i]: float(prob[i]) * 100 for i in range(len(self.classNames))}
        return PredictionResult(
            label=self.classNames[idx],
            confidence=float(prob[idx]) * 100,
            probHuman=p[Label.HUMAN_ART],
            probAI=p[Label.AI_ART],
        )


# ---------------------------------------------------------------------------
# GradCAMGenerator
# ---------------------------------------------------------------------------
class GradCAMGenerator:
    """-targetLayer: String | +buatHeatmap(image, label): Heatmap | +gabungOverlay(image, heatmap): Image"""

    def __init__(self, classifier: SwinClassifier,
                 targetLayer: str = "layers[-1].blocks[-1].norm1"):
        self.classifier = classifier
        self.targetLayer = targetLayer
        self._cam = None

    def _layerTarget(self):
        m = self.classifier.model
        return m.layers[-1].blocks[-1].norm1  # == self.targetLayer

    def _gradcam(self):
        if self._cam is None:
            from pytorch_grad_cam import GradCAM
            self.classifier._pastikanTermuat()
            self._cam = GradCAM(model=self.classifier.model,
                                target_layers=[self._layerTarget()],
                                reshape_transform=reshape_transform)
        return self._cam

    def buatHeatmap(self, image: Image.Image, label: Label) -> Heatmap:
        from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

        cam = self._gradcam()
        x = self.classifier.preprocessor.transformasi(image).to(self.classifier.device)
        target = self.classifier.classNames.index(label)
        with self.classifier.lock:
            heat = cam(input_tensor=x, targets=[ClassifierOutputTarget(target)])[0]
        return heat

    def gabungOverlay(self, image: Image.Image, heatmap: Heatmap) -> Image.Image:
        from pytorch_grad_cam.utils.image import show_cam_on_image

        size = self.classifier.preprocessor.imageSize
        img = image.convert("RGB")
        if MATCH_TRAINING:
            img = Preprocessor.samakanDataLatih(img)
        img224 = np.asarray(img.resize((size, size)))
        overlay = show_cam_on_image(img224.astype(np.float32) / 255.0, heatmap, use_rgb=True)
        return Image.fromarray(overlay)
