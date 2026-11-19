"""Layanan autentikasi Art_ku (sesuai Class Diagram).

- FirebaseAuthClient : jembatan ke "Layanan Firebase Auth".
    * verifikasiIdToken memakai firebase-admin + ./serviceAccountKey.json.
    * buatAkun / masukDenganEmail / kirimEmailReset memakai Firebase Auth REST API
      (endpoint yang sama dengan yang dipakai Firebase JS SDK:
      createUserWithEmailAndPassword, signInWithEmailAndPassword, sendPasswordResetEmail).
    * masukDenganGoogle hanya bisa dijalankan di browser (signInWithPopup + GoogleAuthProvider)
      lewat Firebase JS SDK, lihat static/js/firebase-config.js.
- AuthService        : verifikasi token, pembuatan/penghapusan sesi Flask, penjaga akses.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials
from flask import g, session

from models.entities import Pengguna
from repositories.repositories import UserRepository


class FirebaseAuthError(Exception):
    """Kesalahan dari Layanan Firebase Auth (pesan sudah berbahasa Indonesia)."""


_PESAN_FIREBASE = {
    "EMAIL_EXISTS": "Email sudah terdaftar. Silakan masuk.",
    "INVALID_EMAIL": "Format email tidak valid.",
    "WEAK_PASSWORD": "Kata sandi minimal 8 karakter.",
    "PASSWORD_DOES_NOT_MEET_REQUIREMENTS": "Kata sandi minimal 8 karakter.",
    "EMAIL_NOT_FOUND": "Email atau kata sandi salah.",
    "INVALID_PASSWORD": "Email atau kata sandi salah.",
    "INVALID_LOGIN_CREDENTIALS": "Email atau kata sandi salah.",
    "USER_DISABLED": "Akun ini dinonaktifkan.",
    "TOO_MANY_ATTEMPTS_TRY_LATER": "Terlalu banyak percobaan. Coba lagi nanti.",
}


# ---------------------------------------------------------------------------
# FirebaseAuthClient
# ---------------------------------------------------------------------------
class FirebaseAuthClient:
    """-projectId: String"""

    REST_BASE = "https://identitytoolkit.googleapis.com/v1"

    def __init__(self, credentialPath: str = "./serviceAccountKey.json",
                 apiKey: Optional[str] = None, projectId: Optional[str] = None):
        self.credentialPath = str(credentialPath)
        self.apiKey = apiKey or os.getenv("FIREBASE_API_KEY", "")
        self.projectId = projectId or os.getenv("FIREBASE_PROJECT_ID", "")
        self._app = None

    # -- inisialisasi firebase-admin (sekali saja) --------------------------
    def _adminApp(self):
        if self._app is not None:
            return self._app
        try:
            self._app = firebase_admin.get_app()
        except ValueError:
            path = Path(self.credentialPath)
            if not path.exists():
                raise FirebaseAuthError(
                    f"File kredensial Firebase tidak ditemukan: {path}. "
                    "Letakkan serviceAccountKey.json di folder proyek."
                )
            cred = credentials.Certificate(str(path))
            self._app = firebase_admin.initialize_app(cred)
        if not self.projectId:
            self.projectId = self._app.project_id or ""
        return self._app

    # -- REST helper ---------------------------------------------------------
    def _rest(self, endpoint: str, payload: dict) -> dict:
        if not self.apiKey:
            raise FirebaseAuthError("FIREBASE_API_KEY belum dikonfigurasi.")
        url = f"{self.REST_BASE}/{endpoint}?key={self.apiKey}"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                kode = json.loads(e.read().decode("utf-8"))["error"]["message"]
            except Exception:
                kode = "UNKNOWN"
            kunci = kode.split(" ")[0].split(":")[0]
            raise FirebaseAuthError(_PESAN_FIREBASE.get(kunci, f"Firebase Auth: {kode}")) from e
        except urllib.error.URLError as e:
            raise FirebaseAuthError("Tidak dapat terhubung ke Layanan Firebase Auth.") from e

    # -- method sesuai Class Diagram -----------------------------------------
    def buatAkun(self, email: str, sandi: str) -> str:
        """Membuat akun email & kata sandi. Mengembalikan ID token."""
        data = self._rest("accounts:signUp",
                          {"email": email, "password": sandi, "returnSecureToken": True})
        return data["idToken"]

    def masukDenganEmail(self, email: str, sandi: str) -> str:
        """Masuk dengan email & kata sandi. Mengembalikan ID token."""
        data = self._rest("accounts:signInWithPassword",
                          {"email": email, "password": sandi, "returnSecureToken": True})
        return data["idToken"]

    def masukDenganGoogle(self) -> str:
        """Masuk dengan Google membutuhkan popup di browser.

        Dijalankan oleh Firebase JS SDK (`signInWithPopup(auth, new GoogleAuthProvider())`)
        pada Antarmuka Web; ID token hasilnya dikirim ke WebController.lanjutkanDenganGoogle().
        """
        raise FirebaseAuthError(
            "masukDenganGoogle() dijalankan di browser melalui Firebase JS SDK (signInWithPopup)."
        )

    def kirimEmailReset(self, email: str) -> None:
        """sendPasswordResetEmail(email): Firebase mengirim email tautan pemulihan."""
        self._rest("accounts:sendOobCode", {"requestType": "PASSWORD_RESET", "email": email})

    def verifikasiIdToken(self, token: str) -> Optional[str]:
        """Memverifikasi ID token Firebase. Mengembalikan uid bila valid, None bila tidak."""
        self._adminApp()
        try:
            klaim = fb_auth.verify_id_token(token, clock_skew_seconds=10)
        except (fb_auth.InvalidIdTokenError, fb_auth.ExpiredIdTokenError,
                fb_auth.RevokedIdTokenError, fb_auth.CertificateFetchError,
                fb_auth.UserDisabledError, ValueError):
            return None
        # Klaim disimpan per-permintaan agar AuthService dapat membaca email pengguna.
        g.firebase_klaim = klaim
        return klaim.get("uid")


# ---------------------------------------------------------------------------
# AuthService
# ---------------------------------------------------------------------------
class AuthService:
    """-sessionTimeoutMenit: int"""

    def __init__(self, firebaseClient: FirebaseAuthClient, userRepository: UserRepository,
                 sessionTimeoutMenit: int = 30):
        self.firebaseClient = firebaseClient
        self.userRepository = userRepository
        self.sessionTimeoutMenit = int(sessionTimeoutMenit)

    def verifikasiToken(self, token: str) -> bool:
        """Sequence Registrasi/Login:
        verifikasiIdToken(token) -> uid valid -> cariBerdasarkanUid(uid)
        -> [kosong / akun baru] simpan(pengguna) -> status verifikasi (valid).

        Pengguna terverifikasi tersedia di `flask.g.pengguna_terverifikasi`.
        """
        g.pengguna_terverifikasi = None
        if not token:
            return False

        uid = self.firebaseClient.verifikasiIdToken(token)
        if not uid:
            return False

        pengguna = self.userRepository.cariBerdasarkanUid(uid)
        if pengguna is None:  # kosong (akun baru)
            email = (getattr(g, "firebase_klaim", {}) or {}).get("email", "")
            pengguna = Pengguna(id=None, email=email, firebaseUid=uid)
            self.userRepository.simpan(pengguna)
            if not pengguna.id:
                return False

        g.pengguna_terverifikasi = pengguna
        return True

    def kirimTautanPemulihan(self, email: str) -> None:
        """Meneruskan permintaan ke Firebase. Status selalu netral (tidak membocorkan
        apakah email terdaftar atau tidak)."""
        try:
            self.firebaseClient.kirimEmailReset(email)
        except FirebaseAuthError:
            pass  # status netral

    def buatSesi(self, pengguna: Pengguna) -> None:
        session.clear()
        session.permanent = True
        session["user_id"] = pengguna.id
        session["email"] = pengguna.email
        session["firebase_uid"] = pengguna.firebaseUid
        session["aktivitas_terakhir"] = datetime.now(timezone.utc).isoformat()

    def hapusSesi(self) -> None:
        session.clear()

    def cekStatusLogin(self) -> bool:
        """Penjaga akses: sesi ada dan belum melewati sessionTimeoutMenit sejak aktivitas terakhir."""
        if not session.get("user_id"):
            return False
        try:
            terakhir = datetime.fromisoformat(session.get("aktivitas_terakhir", ""))
        except (TypeError, ValueError):
            self.hapusSesi()
            return False
        sekarang = datetime.now(timezone.utc)
        if sekarang - terakhir > timedelta(minutes=self.sessionTimeoutMenit):
            self.hapusSesi()  # sesi kedaluwarsa
            return False
        session["aktivitas_terakhir"] = sekarang.isoformat()  # perpanjang (sliding)
        return True
