"""WebController Art_ku (sesuai Class Diagram, Sequence Diagram s1–s6, & Activity Diagram a1–a6).

Method publik wajib pada WebController:
- halamanMasuk() -> Response
- halamanDaftar() -> Response
- daftar(email, sandi, konfirmasi) -> Response
- login(email, sandi) -> Response
- lanjutkanDenganGoogle() -> Response
- lupaKataSandi(email) -> Response
- logout() -> Response
- bukaStudio() -> Response
- analisisGambar(file) -> AnalysisResult
- lihatHasil(id) -> Response
- bukaRiwayat(filter, urutan) -> Response
- hapusRiwayat(id) -> Response
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from flask import (
    Response,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from PIL import Image

from models.entities import AnalysisResult, HistoryRecord, Label
from repositories.repositories import FileStorage, HistoryRepository, UserRepository
from services.auth_service import AuthService, FirebaseAuthError
from services.classifier_service import GradCAMGenerator, SwinClassifier

FORMAT_DIIZINKAN = {".jpg", ".jpeg", ".png", ".webp"}
MAKS_UKURAN_BYTES = 10 * 1024 * 1024  # 10 MB


class WebController:
    """Pengendali utama antarmuka web dan endpoint Art_ku."""

    def __init__(
        self,
        authService: AuthService,
        userRepository: UserRepository,
        historyRepository: HistoryRepository,
        fileStorage: FileStorage,
        classifier: SwinClassifier,
        gradcamGenerator: GradCAMGenerator,
    ):
        self.authService = authService
        self.userRepository = userRepository
        self.historyRepository = historyRepository
        self.fileStorage = fileStorage
        self.classifier = classifier
        self.gradcamGenerator = gradcamGenerator

    # -----------------------------------------------------------------------
    # Helper internal
    # -----------------------------------------------------------------------
    @staticmethod
    def _apakahJson() -> bool:
        if request.is_json:
            return True
        accept = request.headers.get("Accept", "")
        return "application/json" in accept or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    @staticmethod
    def _ambilTokenDariRequest() -> Optional[str]:
        if request.is_json:
            body = request.get_json(silent=True) or {}
            if body.get("idToken") or body.get("token"):
                return body.get("idToken") or body.get("token")
        authHeader = request.headers.get("Authorization", "")
        if authHeader.startswith("Bearer "):
            return authHeader[7:].strip()
        return request.form.get("idToken") or request.form.get("token")

    def _selesaikanAutentikasiToken(self, token: str) -> Response:
        """Langkah bersama Sequence Diagram Registrasi & Login setelah memperoleh ID Token:
        1. AuthService.verifikasiToken(token)
             -> FirebaseAuthClient.verifikasiIdToken(token) -> uid valid
             -> UserRepository.cariBerdasarkanUid(uid)
             -> [kosong / akun baru] UserRepository.simpan(pengguna)
        2. AuthService.buatSesi(pengguna)
        3. Arahkan ke halaman utama Studio Analisis (bukaStudio).
        """
        valid = self.authService.verifikasiToken(token)
        pengguna = getattr(g, "pengguna_terverifikasi", None)
        if not valid or pengguna is None:
            pesan = "Kredensial atau sesi tidak valid / kedaluwarsa. Silakan coba lagi."
            if self._apakahJson():
                return jsonify(ok=False, error=pesan), 401
            return render_template("auth.html", mode="masuk", error=pesan), 401

        self.authService.buatSesi(pengguna)
        tujuan = url_for("buka_studio")
        if self._apakahJson():
            return jsonify(
                ok=True,
                redirect=tujuan,
                pengguna={"id": pengguna.id, "email": pengguna.email, "firebaseUid": pengguna.firebaseUid},
            )
        return redirect(tujuan)

    # -----------------------------------------------------------------------
    # 1. Halaman Masuk & Daftar
    # -----------------------------------------------------------------------
    def halamanMasuk(self) -> Response:
        if self.authService.cekStatusLogin():
            return redirect(url_for("buka_studio"))
        statusPesan = request.args.get("pesan")
        info = None
        if statusPesan == "sesi_berakhir":
            info = "Sesi kamu berakhir, silakan masuk lagi"
        elif statusPesan == "sudah_keluar":
            info = "Kamu sudah keluar"
        return Response(render_template("auth.html", mode="masuk", info=info))

    def halamanDaftar(self) -> Response:
        if self.authService.cekStatusLogin():
            return redirect(url_for("buka_studio"))
        return Response(render_template("auth.html", mode="daftar"))

    # -----------------------------------------------------------------------
    # 2. Registrasi, Login, Google Auth, Reset Sandi, Logout
    # -----------------------------------------------------------------------
    def daftar(
        self,
        email: Optional[str] = None,
        sandi: Optional[str] = None,
        konfirmasi: Optional[str] = None,
    ) -> Response:
        """Sequence Diagram - Registrasi (s1) & Activity Diagram - Registrasi (a1)."""
        token = self._ambilTokenDariRequest()
        if request.is_json:
            body = request.get_json(silent=True) or {}
            email = email if email is not None else body.get("email", "")
            sandi = sandi if sandi is not None else body.get("sandi", "")
            konfirmasi = konfirmasi if konfirmasi is not None else body.get("konfirmasi", "")
        else:
            email = email if email is not None else request.form.get("email", "")
            sandi = sandi if sandi is not None else request.form.get("sandi", "")
            konfirmasi = konfirmasi if konfirmasi is not None else request.form.get("konfirmasi", "")

        # Jika ID token sudah dikirim dari Firebase JS SDK (createUserWithEmailAndPassword):
        if token:
            return self._selesaikanAutentikasiToken(token)

        # Fallback apabila form dikirim langsung ke backend:
        if (sandi or "") != (konfirmasi or ""):
            pesan = "Konfirmasi kata sandi tidak cocok."
            if self._apakahJson():
                return jsonify(ok=False, error=pesan), 400
            return render_template("auth.html", mode="daftar", error=pesan, email=email), 400

        if len(sandi or "") < 8:
            pesan = "Kata sandi minimal 8 karakter."
            if self._apakahJson():
                return jsonify(ok=False, error=pesan), 400
            return render_template("auth.html", mode="daftar", error=pesan, email=email), 400

        try:
            idToken = self.authService.firebaseClient.buatAkun(email or "", sandi or "")
        except FirebaseAuthError as err:
            pesan = str(err)
            if self._apakahJson():
                return jsonify(ok=False, error=pesan), 400
            return render_template("auth.html", mode="daftar", error=pesan, email=email), 400

        return self._selesaikanAutentikasiToken(idToken)

    def login(self, email: Optional[str] = None, sandi: Optional[str] = None) -> Response:
        """Sequence Diagram - Login (s2) & Activity Diagram - Login (a2)."""
        token = self._ambilTokenDariRequest()
        if request.is_json:
            body = request.get_json(silent=True) or {}
            email = email if email is not None else body.get("email", "")
            sandi = sandi if sandi is not None else body.get("sandi", "")
        else:
            email = email if email is not None else request.form.get("email", "")
            sandi = sandi if sandi is not None else request.form.get("sandi", "")

        # Jika ID token diperoleh dari Firebase JS SDK (signInWithEmailAndPassword):
        if token:
            return self._selesaikanAutentikasiToken(token)

        try:
            idToken = self.authService.firebaseClient.masukDenganEmail(email or "", sandi or "")
        except FirebaseAuthError as err:
            pesan = str(err)
            if self._apakahJson():
                return jsonify(ok=False, error=pesan), 401
            return render_template("auth.html", mode="masuk", error=pesan, email=email), 401

        return self._selesaikanAutentikasiToken(idToken)

    def lanjutkanDenganGoogle(self) -> Response:
        """Sequence Diagram - Login dengan Google (s2 langkah 4–16)."""
        token = self._ambilTokenDariRequest()
        if not token:
            pesan = "Otorisasi Google gagal atau token tidak ditemukan."
            if self._apakahJson():
                return jsonify(ok=False, error=pesan), 400
            return render_template("auth.html", mode="masuk", error=pesan), 400
        return self._selesaikanAutentikasiToken(token)

    def lupaKataSandi(self, email: Optional[str] = None) -> Response:
        """Sequence Diagram - Reset Kata Sandi (s5) & Activity Diagram (a5)."""
        if request.method == "GET":
            return Response(render_template("lupa_sandi.html", terkirim=False))

        if request.is_json:
            body = request.get_json(silent=True) or {}
            email = email if email is not None else body.get("email", "")
        else:
            email = email if email is not None else request.form.get("email", "")

        email = (email or "").strip()
        if not email or "@" not in email or "." not in email.split("@")[-1]:
            pesan = "Format email tidak valid. Contoh: nama@email.com"
            if self._apakahJson():
                return jsonify(ok=False, error=pesan), 400
            return render_template("lupa_sandi.html", terkirim=False, error=pesan, email=email), 400

        # Panggil AuthService.kirimTautanPemulihan(email) -> pesan netral
        self.authService.kirimTautanPemulihan(email)
        pesanNetral = "Periksa kotak masuk Anda untuk tautan pemulihan kata sandi"
        if self._apakahJson():
            return jsonify(ok=True, pesan=pesanNetral, email=email)
        return Response(render_template("lupa_sandi.html", terkirim=True, pesan=pesanNetral, email=email))

    def logout(self) -> Response:
        """Sequence Diagram - Logout (s6) & Activity Diagram - Logout (a6)."""
        self.authService.hapusSesi()
        tujuan = url_for("halaman_masuk", pesan="sudah_keluar")
        if self._apakahJson():
            return jsonify(ok=True, redirect=tujuan)
        return redirect(tujuan)

    # -----------------------------------------------------------------------
    # 3. Studio Analisis & Klasifikasi Gambar
    # -----------------------------------------------------------------------
    def bukaStudio(self) -> Response:
        """Sequence Diagram - Klasifikasi (s3 langkah 1–3, 30)."""
        if not self.authService.cekStatusLogin():
            return redirect(url_for("halaman_masuk", pesan="sesi_berakhir"))
        return Response(
            render_template(
                "studio.html",
                emailPengguna=session.get("email", ""),
                hasilAwal=None,
            )
        )

    def analisisGambar(self, file: Any = None) -> AnalysisResult:
        """Sequence Diagram - Klasifikasi (s3 langkah 11–28):
        1. AuthService.cekStatusLogin()
        2. SwinClassifier.prediksi(image) -> Preprocessor.transformasi(image)
        3. GradCAMGenerator.buatHeatmap(image, label) + gabungOverlay(image, heatmap)
        4. FileStorage.simpanFile(gambar, "original") -> imagePath
        5. FileStorage.simpanFile(heatmap, "heatmap") -> heatmapPath
        6. HistoryRepository.simpan(record)
        7. Kembalikan AnalysisResult.
        """
        if not self.authService.cekStatusLogin():
            raise PermissionError("Sesi kamu berakhir, silakan masuk lagi")

        unggahan = file if file is not None else (
            request.files.get("file") or request.files.get("image")
        )
        if unggahan is None or not getattr(unggahan, "filename", ""):
            raise ValueError("Pilih gambar terlebih dahulu.")

        namaAsli = Path(unggahan.filename).name
        ekstensi = Path(namaAsli).suffix.lower()
        if ekstensi not in FORMAT_DIIZINKAN:
            raise ValueError("Format tidak didukung. Pilih JPG, JPEG, PNG, atau WEBP.")

        unggahan.stream.seek(0, 2)
        ukuran = unggahan.stream.tell()
        unggahan.stream.seek(0)
        if ukuran > MAKS_UKURAN_BYTES:
            raise ValueError("Ukuran melebihi 10 MB. Maksimal 10 MB.")

        try:
            image = Image.open(unggahan.stream).convert("RGB")
        except Exception as err:
            raise ValueError("File bukan gambar yang valid.") from err

        # Langkah 15–18: prediksi(image) -> transformasi(image) -> tensor -> PredictionResult
        prediction = self.classifier.prediksi(image)

        # Langkah 19–20: buatHeatmap(image, label) -> heatmap & overlay Grad-CAM
        rawHeatmap = self.gradcamGenerator.buatHeatmap(image, prediction.label)
        overlayImage = self.gradcamGenerator.gabungOverlay(image, rawHeatmap)

        # Langkah 21–24: simpanFile(gambar, "original") & simpanFile(heatmap, "heatmap")
        unggahan.stream.seek(0)
        imagePath = self.fileStorage.simpanFile(unggahan, "original")
        heatmapPath = self.fileStorage.simpanFile(overlayImage, "heatmap")

        # Langkah 25–26: HistoryRepository.simpan(record)
        userId = int(session["user_id"])
        waktu = datetime.now()
        record = HistoryRecord(
            id=None,
            userId=userId,
            fileName=namaAsli,
            imagePath=imagePath,
            label=prediction.label,
            confidence=round(prediction.confidence, 1),
            heatmapPath=heatmapPath,
            timestamp=waktu,
        )
        self.historyRepository.simpan(record)

        return AnalysisResult(
            prediction=prediction,
            heatmap=overlayImage,
            _ekstra={
                "historyId": record.id,
                "fileName": namaAsli,
                "imagePath": imagePath,
                "heatmapPath": heatmapPath,
                "imageUrl": url_for("static", filename=imagePath),
                "heatmapUrl": url_for("static", filename=heatmapPath),
                "timestamp": waktu.strftime("%d %b %Y, %H:%M"),
            },
        )

    # -----------------------------------------------------------------------
    # 4. Riwayat Klasifikasi (Lihat, Filter/Urut, Hapus, Lihat Hasil)
    # -----------------------------------------------------------------------
    def bukaRiwayat(
        self,
        filter: Optional[str] = None,
        urutan: Optional[str] = None,
    ) -> Response:
        """Sequence Diagram - Riwayat (s4 langkah 1–12, 28)."""
        if not self.authService.cekStatusLogin():
            if self._apakahJson():
                return jsonify(ok=False, redirect=url_for("halaman_masuk", pesan="sesi_berakhir")), 401
            return redirect(url_for("halaman_masuk", pesan="sesi_berakhir"))

        filterAktif = (filter or request.args.get("filter") or "semua").lower()
        urutanAktif = (urutan or request.args.get("urutan") or "terbaru").lower()
        userId = int(session["user_id"])

        daftarRiwayat = self.historyRepository.ambilBerdasarkanPengguna(
            userId=userId, filter=filterAktif, urutan=urutanAktif
        )
        ringkasan = self.historyRepository.ambilRingkasan(userId=userId)

        if self._apakahJson():
            return jsonify(
                ok=True,
                filter=filterAktif,
                urutan=urutanAktif,
                ringkasan=ringkasan.keDict(),
                riwayat=[
                    {
                        **r.keDict(),
                        "imageUrl": url_for("static", filename=r.imagePath),
                        "heatmapUrl": url_for("static", filename=r.heatmapPath),
                        "waktuTeks": r.timestamp.strftime("%d %b %Y, %H:%M"),
                    }
                    for r in daftarRiwayat
                ],
            )

        return Response(
            render_template(
                "riwayat.html",
                emailPengguna=session.get("email", ""),
                riwayat=daftarRiwayat,
                ringkasan=ringkasan,
                filterAktif=filterAktif,
                urutanAktif=urutanAktif,
            )
        )

    def lihatHasil(self, id: int) -> Response:
        """Sequence Diagram - Riwayat (s4 langkah 24–27):
        ambilBerdasarkanId(id) -> record riwayat -> tampilkanPanelHasil().
        """
        if not self.authService.cekStatusLogin():
            if self._apakahJson():
                return jsonify(ok=False, redirect=url_for("halaman_masuk", pesan="sesi_berakhir")), 401
            return redirect(url_for("halaman_masuk", pesan="sesi_berakhir"))

        record = self.historyRepository.ambilBerdasarkanId(int(id))
        userId = int(session["user_id"])
        if record is None or record.userId != userId:
            pesan = "Data riwayat tidak ditemukan."
            if self._apakahJson():
                return jsonify(ok=False, error=pesan), 404
            return redirect(url_for("buka_riwayat"))

        # Hitung probHuman & probAI dari label + confidence tersimpan
        conf = round(float(record.confidence), 1)
        if record.label is Label.AI_ART:
            probAI = conf
            probHuman = round(max(0.0, 100.0 - conf), 1)
        else:
            probHuman = conf
            probAI = round(max(0.0, 100.0 - conf), 1)

        dataHasil = {
            **record.keDict(),
            "probHuman": probHuman,
            "probAI": probAI,
            "imageUrl": url_for("static", filename=record.imagePath),
            "heatmapUrl": url_for("static", filename=record.heatmapPath),
            "waktuTeks": record.timestamp.strftime("%d %b %Y, %H:%M"),
        }

        if self._apakahJson():
            return jsonify(ok=True, hasil=dataHasil)

        return Response(
            render_template(
                "studio.html",
                emailPengguna=session.get("email", ""),
                hasilAwal=dataHasil,
            )
        )

    def hapusRiwayat(self, id: int) -> Response:
        """Sequence Diagram - Riwayat (s4 langkah 13–22):
        1. HistoryRepository.hapus(id)
        2. FileStorage.hapusFile(imagePath)
        3. FileStorage.hapusFile(heatmapPath)
        """
        if not self.authService.cekStatusLogin():
            if self._apakahJson():
                return jsonify(ok=False, redirect=url_for("halaman_masuk", pesan="sesi_berakhir")), 401
            return redirect(url_for("halaman_masuk", pesan="sesi_berakhir"))

        record = self.historyRepository.ambilBerdasarkanId(int(id))
        userId = int(session["user_id"])
        if record is None or record.userId != userId:
            if self._apakahJson():
                return jsonify(ok=False, error="Riwayat tidak ditemukan."), 404
            return redirect(url_for("buka_riwayat"))

        # Urutan persis Sequence Diagram s4 langkah 16 -> 18 -> 20
        self.historyRepository.hapus(int(id))
        self.fileStorage.hapusFile(record.imagePath)
        self.fileStorage.hapusFile(record.heatmapPath)

        ringkasan = self.historyRepository.ambilRingkasan(userId=userId)
        if self._apakahJson():
            return jsonify(ok=True, dihapusId=int(id), ringkasan=ringkasan.keDict())
        return redirect(url_for("buka_riwayat"))
