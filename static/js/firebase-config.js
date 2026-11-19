/* =========================================================
   firebase-config.js
   Konfigurasi Firebase JS SDK & alur autentikasi front-end Art_ku
   Sesuai Sequence Diagram s1, s2, s5, s6 & Activity Diagram a1, a2, a5, a6.
   ========================================================= */

const firebaseConfig = {
  apiKey: "AIzaSyAyWqlSA0ySYVdjn4xWoVuffOj40Q_6Sfc",
  authDomain: "artku-525cd.firebaseapp.com",
  projectId: "artku-525cd",
  storageBucket: "artku-525cd.firebasestorage.app",
  messagingSenderId: "71113691491",
  appId: "1:71113691491:web:73fdf729eae7a102610356",
  measurementId: "G-MDGXGTL6QZ"
};

// Inisialisasi Firebase JS SDK (compat) bila tersedia di halaman
let firebaseAuth = null;
let googleProvider = null;

if (typeof firebase !== "undefined") {
  if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
  }
  firebaseAuth = firebase.auth();
  googleProvider = new firebase.auth.GoogleAuthProvider();
}

// ---------------------------------------------------------------------------
// Pemetaan kode error Firebase -> pesan Bahasa Indonesia sesuai wireframe PDF
// ---------------------------------------------------------------------------
function terjemahkanErrorFirebase(err) {
  const code = (err && err.code) || "";
  if (code.includes("email-already-in-use")) {
    return { field: "email", pesan: "Email sudah terdaftar. Silakan masuk." };
  }
  if (code.includes("invalid-email")) {
    return { field: "email", pesan: "Format email tidak valid. Contoh: nama@email.com" };
  }
  if (code.includes("weak-password")) {
    return { field: "sandi", pesan: "Kata sandi minimal 8 karakter." };
  }
  if (
    code.includes("wrong-password") ||
    code.includes("user-not-found") ||
    code.includes("invalid-credential") ||
    code.includes("invalid-login-credentials")
  ) {
    return { field: "global", pesan: "Email atau kata sandi salah. Coba lagi." };
  }
  if (code.includes("too-many-requests")) {
    return {
      field: "global",
      pesan: "Terlalu sering meminta. Tunggu beberapa saat sebelum mencoba lagi.",
      terlaluSering: true
    };
  }
  if (code.includes("popup-closed-by-user") || code.includes("cancelled-popup-request")) {
    return { field: "global", pesan: "Otorisasi Google dibatalkan." };
  }
  return { field: "global", pesan: (err && err.message) || "Terjadi kesalahan autentikasi. Coba lagi." };
}

// ---------------------------------------------------------------------------
// Method sesuai Sequence Diagram s1, s2, s5:
// - cekKonfirmasiSandi(sandi, konfirmasi)
// - tampilkanPesanError(pesan, targetId)
// - daftar(email, sandi, konfirmasi) -> createUserWithEmailAndPassword
// - login(email, sandi) -> signInWithEmailAndPassword
// - lanjutkanDenganGoogle() -> signInWithPopup(GoogleAuthProvider)
// - lupaKataSandi(email) -> sendPasswordResetEmail(email)
// ---------------------------------------------------------------------------
function cekKonfirmasiSandi(sandi, konfirmasi) {
  return sandi === konfirmasi;
}

function tampilkanPesanError(pesan, targetEl) {
  const el = typeof targetEl === "string" ? document.getElementById(targetEl) : targetEl;
  if (!el) return;
  el.textContent = pesan;
  el.hidden = !pesan;
}

function tampilkanHalamanUtama(urlTujuan) {
  window.location.href = urlTujuan || "/studio";
}

async function kirimTokenKeBackend(endpoint, idToken, payloadTambahan = {}) {
  const resp = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json"
    },
    body: JSON.stringify({ idToken, ...payloadTambahan })
  });
  let data = {};
  try {
    data = await resp.json();
  } catch (_) {}
  return { ok: resp.ok && data.ok !== false, status: resp.status, data };
}

// Ekspos ke global window agar dapat dipanggil dari halaman Masuk, Daftar, & Lupa Kata Sandi
window.ArtKuAuth = {
  firebaseConfig,
  cekKonfirmasiSandi,
  tampilkanPesanError,
  tampilkanHalamanUtama,
  terjemahkanErrorFirebase,

  async buatAkun(email, sandi) {
    if (!firebaseAuth) {
      throw new Error("Firebase Auth SDK belum termuat.");
    }
    const cred = await firebaseAuth.createUserWithEmailAndPassword(email, sandi);
    return await cred.user.getIdToken();
  },

  async masukDenganEmail(email, sandi) {
    if (!firebaseAuth) {
      throw new Error("Firebase Auth SDK belum termuat.");
    }
    const cred = await firebaseAuth.signInWithEmailAndPassword(email, sandi);
    return await cred.user.getIdToken();
  },

  async masukDenganGoogle() {
    if (!firebaseAuth || !googleProvider) {
      throw new Error("Firebase Auth SDK belum termuat.");
    }
    const cred = await firebaseAuth.signInWithPopup(googleProvider);
    return await cred.user.getIdToken();
  },

  async kirimEmailReset(email) {
    if (firebaseAuth) {
      await firebaseAuth.sendPasswordResetEmail(email);
    }
  },

  kirimTokenKeBackend
};
