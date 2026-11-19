"""Entitas domain Art_ku (sesuai Class Diagram).

Kelas: Label (enumeration), Pengguna, PredictionResult, AnalysisResult,
HistoryRecord, HistorySummary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class Label(str, Enum):
    """«enumeration» Label."""

    HUMAN_ART = "HUMAN_ART"
    AI_ART = "AI_ART"

    @property
    def teks(self) -> str:
        """Teks label untuk ditampilkan di antarmuka."""
        return "Human Art" if self is Label.HUMAN_ART else "AI Art"


@dataclass
class Pengguna:
    """Pengguna lokal (tabel MySQL `pengguna`)."""

    id: Optional[int]
    email: str
    firebaseUid: str


@dataclass
class PredictionResult:
    """Hasil prediksi SwinClassifier."""

    label: Label
    confidence: float   # persen 0..100
    probHuman: float    # persen 0..100
    probAI: float       # persen 0..100


@dataclass
class AnalysisResult:
    """Hasil analisis lengkap: prediksi + heatmap Grad-CAM."""

    prediction: PredictionResult
    heatmap: Any  # Image (PIL) atau URL heatmap yang telah disimpan
    # Informasi pendukung untuk antarmuka (bukan bagian inti diagram).
    _ekstra: dict = field(default_factory=dict, repr=False)

    def keDict(self) -> dict:
        p = self.prediction
        data = {
            "label": p.label.value,
            "labelTeks": p.label.teks,
            "confidence": round(p.confidence, 1),
            "probHuman": round(p.probHuman, 1),
            "probAI": round(p.probAI, 1),
            "heatmap": self.heatmap if isinstance(self.heatmap, str) else None,
        }
        data.update(self._ekstra)
        return data


@dataclass
class HistoryRecord:
    """Satu baris riwayat klasifikasi (tabel MySQL `history_record`)."""

    id: Optional[int]
    userId: int
    fileName: str
    imagePath: str
    label: Label
    confidence: float
    heatmapPath: str
    timestamp: datetime

    def keDict(self) -> dict:
        return {
            "id": self.id,
            "userId": self.userId,
            "fileName": self.fileName,
            "imagePath": self.imagePath,
            "label": self.label.value,
            "labelTeks": self.label.teks,
            "confidence": round(float(self.confidence), 1),
            "heatmapPath": self.heatmapPath,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        }


@dataclass
class HistorySummary:
    """Ringkasan riwayat milik seorang pengguna."""

    total: int
    jumlahAIArt: int
    jumlahHumanArt: int

    def keDict(self) -> dict:
        return {
            "total": self.total,
            "jumlahAIArt": self.jumlahAIArt,
            "jumlahHumanArt": self.jumlahHumanArt,
        }
