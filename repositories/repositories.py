"""Lapisan penyimpanan Art_ku (sesuai Class Diagram).

- Database          : tipe atribut `storage` (koneksi MySQL `art_ku_db`)
- UserRepository    : data pengguna lokal (tabel `pengguna`)
- HistoryRepository : riwayat klasifikasi (tabel `history_record`)
- FileStorage       : file gambar asli & heatmap di `static/uploads/`
"""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

import mysql.connector

from models.entities import HistoryRecord, HistorySummary, Label, Pengguna


# ---------------------------------------------------------------------------
# Database (tipe untuk atribut `storage`)
# ---------------------------------------------------------------------------
class Database:
    """Pembungkus koneksi MySQL. Satu koneksi baru per operasi (aman untuk thread)."""

    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port

    @classmethod
    def dariEnv(cls) -> "Database":
        return cls(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "art_ku_db"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
        )

    @contextmanager
    def koneksi(self):
        conn = mysql.connector.connect(
            host=self.host, user=self.user, password=self.password,
            database=self.database, port=self.port,
        )
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def inisialisasi(self) -> None:
        """Membuat database `art_ku_db` beserta tabel `pengguna` & `history_record` bila belum ada."""
        conn = mysql.connector.connect(
            host=self.host, user=self.user, password=self.password, port=self.port,
        )
        try:
            cur = conn.cursor()
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cur.execute(f"USE `{self.database}`")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pengguna (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255),
                    firebase_uid VARCHAR(128) UNIQUE NOT NULL
                ) ENGINE=InnoDB
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS history_record (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    file_name VARCHAR(255),
                    image_path VARCHAR(255),
                    label VARCHAR(50),
                    confidence FLOAT,
                    heatmap_path VARCHAR(255),
                    timestamp DATETIME,
                    CONSTRAINT fk_history_pengguna FOREIGN KEY (user_id)
                        REFERENCES pengguna(id) ON DELETE CASCADE
                ) ENGINE=InnoDB
                """
            )
            conn.commit()
            cur.close()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# UserRepository
# ---------------------------------------------------------------------------
class UserRepository:
    """-storage: Database | +cariBerdasarkanUid(uid): Pengguna | +simpan(pengguna): void"""

    def __init__(self, storage: Database):
        self.storage = storage

    def cariBerdasarkanUid(self, uid: str) -> Optional[Pengguna]:
        with self.storage.koneksi() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT id, email, firebase_uid FROM pengguna WHERE firebase_uid = %s",
                (uid,),
            )
            row = cur.fetchone()
            cur.close()
        if not row:
            return None
        return Pengguna(id=row["id"], email=row["email"], firebaseUid=row["firebase_uid"])

    def simpan(self, pengguna: Pengguna) -> None:
        with self.storage.koneksi() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO pengguna (email, firebase_uid) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE email = VALUES(email)",
                (pengguna.email, pengguna.firebaseUid),
            )
            if cur.lastrowid:
                pengguna.id = cur.lastrowid
            cur.close()
        if not pengguna.id:  # baris sudah ada (duplikat uid): ambil id-nya
            ada = self.cariBerdasarkanUid(pengguna.firebaseUid)
            pengguna.id = ada.id if ada else None


# ---------------------------------------------------------------------------
# HistoryRepository
# ---------------------------------------------------------------------------
class HistoryRepository:
    """Riwayat klasifikasi pada tabel `history_record`."""

    FILTER_VALID = {"semua", "ai", "human"}
    URUTAN_SQL = {
        "terbaru": "timestamp DESC, id DESC",
        "terlama": "timestamp ASC, id ASC",
        "keyakinan_tinggi": "confidence DESC, id DESC",
        "keyakinan_rendah": "confidence ASC, id ASC",
    }

    def __init__(self, storage: Database):
        self.storage = storage

    @staticmethod
    def _keRecord(row: dict) -> HistoryRecord:
        return HistoryRecord(
            id=row["id"],
            userId=row["user_id"],
            fileName=row["file_name"],
            imagePath=row["image_path"],
            label=Label(row["label"]),
            confidence=float(row["confidence"]),
            heatmapPath=row["heatmap_path"],
            timestamp=row["timestamp"],
        )

    def simpan(self, record: HistoryRecord) -> None:
        with self.storage.koneksi() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO history_record
                    (user_id, file_name, image_path, label, confidence, heatmap_path, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.userId, record.fileName, record.imagePath, record.label.value,
                    float(record.confidence), record.heatmapPath, record.timestamp,
                ),
            )
            record.id = cur.lastrowid
            cur.close()

    def ambilBerdasarkanPengguna(self, userId: int, filter: str = "semua",
                                 urutan: str = "terbaru") -> List[HistoryRecord]:
        filter = filter if filter in self.FILTER_VALID else "semua"
        orderBy = self.URUTAN_SQL.get(urutan, self.URUTAN_SQL["terbaru"])
        sql = ("SELECT id, user_id, file_name, image_path, label, confidence, heatmap_path, "
               "timestamp FROM history_record WHERE user_id = %s")
        params: list[Any] = [userId]
        if filter == "ai":
            sql += " AND label = %s"
            params.append(Label.AI_ART.value)
        elif filter == "human":
            sql += " AND label = %s"
            params.append(Label.HUMAN_ART.value)
        sql += f" ORDER BY {orderBy}"  # orderBy berasal dari whitelist
        with self.storage.koneksi() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            cur.close()
        return [self._keRecord(r) for r in rows]

    def ambilBerdasarkanId(self, id: int) -> Optional[HistoryRecord]:
        with self.storage.koneksi() as conn:
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT id, user_id, file_name, image_path, label, confidence, heatmap_path, "
                "timestamp FROM history_record WHERE id = %s",
                (id,),
            )
            row = cur.fetchone()
            cur.close()
        return self._keRecord(row) if row else None

    def hapus(self, id: int) -> None:
        with self.storage.koneksi() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM history_record WHERE id = %s", (id,))
            cur.close()

    def ambilRingkasan(self, userId: int) -> HistorySummary:
        with self.storage.koneksi() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*), "
                "COALESCE(SUM(label = %s), 0), COALESCE(SUM(label = %s), 0) "
                "FROM history_record WHERE user_id = %s",
                (Label.AI_ART.value, Label.HUMAN_ART.value, userId),
            )
            total, ai, human = cur.fetchone()
            cur.close()
        return HistorySummary(total=int(total), jumlahAIArt=int(ai), jumlahHumanArt=int(human))


# ---------------------------------------------------------------------------
# FileStorage
# ---------------------------------------------------------------------------
class FileStorage:
    """-baseDir: String | +simpanFile(file, jenis): String | +hapusFile(path): void

    File disimpan di `<baseDir>/<jenis>/` (jenis: "original" atau "heatmap").
    Nilai kembali berupa path relatif terhadap folder `static`, mis.
    `uploads/original/ab12....png`, sehingga bisa dipakai dengan url_for('static', ...).
    """

    JENIS_VALID = {"original", "heatmap"}

    def __init__(self, baseDir: str):
        self.baseDir = str(baseDir)
        for jenis in self.JENIS_VALID:
            Path(self.baseDir, jenis).mkdir(parents=True, exist_ok=True)

    def _staticRoot(self) -> Path:
        return Path(self.baseDir).resolve().parent  # .../static

    def simpanFile(self, file: Any, jenis: str) -> str:
        if jenis not in self.JENIS_VALID:
            raise ValueError(f"Jenis file tidak dikenal: {jenis}")
        folder = Path(self.baseDir, jenis)

        # 1) PIL.Image (mis. overlay heatmap Grad-CAM) -> PNG
        if hasattr(file, "save") and hasattr(file, "mode") and hasattr(file, "size"):
            nama = f"{uuid.uuid4().hex}.png"
            file.save(folder / nama, format="PNG")
        # 2) werkzeug FileStorage (unggahan asli) -> pertahankan ekstensi
        elif hasattr(file, "filename") and hasattr(file, "stream"):
            ext = Path(file.filename or "").suffix.lower() or ".png"
            nama = f"{uuid.uuid4().hex}{ext}"
            file.stream.seek(0)
            file.save(folder / nama)
        # 3) bytes mentah
        elif isinstance(file, (bytes, bytearray)):
            nama = f"{uuid.uuid4().hex}.bin"
            (folder / nama).write_bytes(file)
        else:
            raise TypeError("Tipe file tidak didukung oleh FileStorage.simpanFile")

        return (folder / nama).resolve().relative_to(self._staticRoot()).as_posix()

    def hapusFile(self, path: str) -> None:
        if not path:
            return
        target = (self._staticRoot() / path).resolve()
        base = Path(self.baseDir).resolve()
        # Cegah penghapusan di luar folder uploads
        if base not in target.parents:
            return
        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
