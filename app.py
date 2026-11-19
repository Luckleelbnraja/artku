"""Entry point aplikasi Flask Art_ku (Sistem Klasifikasi Citra Seni: Human Art vs AI Art).

Menginisialisasi database MySQL (`art_ku_db`), mengatur batas sesi (`sessionTimeoutMenit`),
memuat bobot Swin Transformer (`SwinClassifier.muatBobot()`), serta menghubungkan seluruh
rute HTTP ke `WebController`.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, url_for

from controllers.web_controller import WebController
from repositories.repositories import Database, FileStorage, HistoryRepository, UserRepository
from services.auth_service import AuthService, FirebaseAuthClient
from services.classifier_service import GradCAMGenerator, Preprocessor, SwinClassifier

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SESSION_TIMEOUT_MENIT = int(os.getenv("SESSION_TIMEOUT_MENIT", "30"))

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.secret_key = os.getenv("SECRET_KEY", "art_ku_secret_key")
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=SESSION_TIMEOUT_MENIT)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # maks 10 MB

# ---------------------------------------------------------------------------
# Inisialisasi Database MySQL, Repository, Service, & Controller
# ---------------------------------------------------------------------------
database = Database.dariEnv()


def inisialisasiDatabase() -> bool:
    """Membuat database `art_ku_db` beserta tabel `pengguna` dan `history_record` bila belum ada."""
    try:
        database.inisialisasi()
        return True
    except Exception as err:
        print(f"[Peringatan MySQL] Gagal menginisialisasi database art_ku_db: {err}")
        return False


userRepository = UserRepository(storage=database)
historyRepository = HistoryRepository(storage=database)
fileStorage = FileStorage(baseDir=str(BASE_DIR / "static" / "uploads"))

firebaseClient = FirebaseAuthClient(
    credentialPath=str(BASE_DIR / "serviceAccountKey.json"),
    apiKey=os.getenv("FIREBASE_API_KEY", "AIzaSyAyWqlSA0ySYVdjn4xWoVuffOj40Q_6Sfc"),
    projectId=os.getenv("FIREBASE_PROJECT_ID", "artku-525cd"),
)
authService = AuthService(
    firebaseClient=firebaseClient,
    userRepository=userRepository,
    sessionTimeoutMenit=SESSION_TIMEOUT_MENIT,
)

preprocessor = Preprocessor(imageSize=224)
classifier = SwinClassifier(
    preprocessor=preprocessor,
    modelFile=BASE_DIR / "models" / "B_no_aug_seed42.pt",
)
gradcamGenerator = GradCAMGenerator(
    classifier=classifier,
    targetLayer="layers[-1].blocks[-1].norm1",
)

webController = WebController(
    authService=authService,
    userRepository=userRepository,
    historyRepository=historyRepository,
    fileStorage=fileStorage,
    classifier=classifier,
    gradcamGenerator=gradcamGenerator,
)


# ---------------------------------------------------------------------------
# Filter Jinja untuk format angka & tanggal Indonesia
# ---------------------------------------------------------------------------
_BULAN_ID = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


@app.template_filter("persen_id")
def filterPersenId(nilai) -> str:
    try:
        return f"{float(nilai):.1f}".replace(".", ",")
    except (TypeError, ValueError):
        return "0,0"


@app.template_filter("tanggal_id")
def filterTanggalId(dt) -> str:
    if not hasattr(dt, "month"):
        return str(dt or "")
    bulan = _BULAN_ID[dt.month - 1]
    return f"{dt.day:02d} {bulan} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"


# ---------------------------------------------------------------------------
# Routing HTTP -> WebController
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def beranda():
    if authService.cekStatusLogin():
        return redirect(url_for("buka_studio"))
    return redirect(url_for("halaman_masuk"))


@app.route("/masuk", methods=["GET"])
def halaman_masuk():
    return webController.halamanMasuk()


@app.route("/daftar", methods=["GET"])
def halaman_daftar():
    return webController.halamanDaftar()


@app.route("/daftar", methods=["POST"])
def proses_daftar():
    return webController.daftar()


@app.route("/login", methods=["POST"])
@app.route("/masuk", methods=["POST"])
def proses_login():
    return webController.login()


@app.route("/auth/google", methods=["POST"])
def lanjutkan_dengan_google():
    return webController.lanjutkanDenganGoogle()


@app.route("/lupa-kata-sandi", methods=["GET", "POST"])
def lupa_kata_sandi():
    return webController.lupaKataSandi()


@app.route("/logout", methods=["POST", "GET"])
def proses_logout():
    return webController.logout()


@app.route("/studio", methods=["GET"])
def buka_studio():
    return webController.bukaStudio()


@app.route("/analisis", methods=["POST"])
def analisis_gambar():
    try:
        hasil = webController.analisisGambar()
        return jsonify(ok=True, **hasil.keDict())
    except PermissionError as err:
        return jsonify(
            ok=False,
            error=str(err),
            redirect=url_for("halaman_masuk", pesan="sesi_berakhir"),
        ), 401
    except ValueError as err:
        return jsonify(ok=False, error=str(err)), 400
    except Exception as err:
        return jsonify(ok=False, error=f"Analisis gagal: {err}"), 500


@app.route("/riwayat", methods=["GET"])
def buka_riwayat():
    return webController.bukaRiwayat()


@app.route("/riwayat/<int:id>", methods=["GET"])
def lihat_hasil(id: int):
    return webController.lihatHasil(id)


@app.route("/riwayat/<int:id>/hapus", methods=["POST", "DELETE"])
def hapus_riwayat(id: int):
    return webController.hapusRiwayat(id)


@app.errorhandler(413)
def file_terlalu_besar(_):
    if request.accept_mimetypes.accept_json:
        return jsonify(ok=False, error="Ukuran melebihi 10 MB. Maksimal 10 MB."), 413
    return "Ukuran melebihi 10 MB.", 413


# Inisialisasi database otomatis ketika modul app.py dijalankan/diimpor
inisialisasiDatabase()


if __name__ == "__main__":
    if classifier.modelFile.exists():
        classifier.muatBobot()
    app.run(host="127.0.0.1", port=5000, debug=False)
