/* =========================================================
   studio.js
   Alur Klasifikasi Gambar & Logout di Studio Analisis Art_ku
   Sesuai Sequence Diagram s3 & s6 serta Activity Diagram a3 & a6.
   ========================================================= */

const MAX_BYTES = 10 * 1024 * 1024; // 10 MB
const FORMAT_VALID_EXT = /\.(jpg|jpeg|png|webp)$/i;
const FORMAT_VALID_MIME = /^image\/(jpeg|jpg|png|webp)$/i;
const RING_LENGTH = 2 * Math.PI * 52;

const $ = (id) => document.getElementById(id);

let fileTerpilih = null;
let gradcamTerbuka = false;

const formatAngkaId = (n) =>
  Number(n || 0).toLocaleString("id-ID", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1
  });

const formatUkuranMb = (bytes) =>
  (bytes / (1024 * 1024)).toLocaleString("id-ID", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1
  }) + " MB";

// ---------------------------------------------------------------------------
// 1. Validasi Front-End (Sequence Diagram s3 langkah 5 & 9)
// ---------------------------------------------------------------------------
function validasiFormatDanUkuranFrontEnd(file) {
  if (!file) {
    return { valid: false, alasan: "kosong", pesan: "Pilih gambar terlebih dahulu." };
  }
  const namaValid = FORMAT_VALID_EXT.test(file.name || "");
  const mimeValid = FORMAT_VALID_MIME.test(file.type || "");
  if (!namaValid && !mimeValid) {
    return {
      valid: false,
      alasan: "format",
      pesan: "Format tidak didukung",
      subPesan: "Pilih JPG, JPEG, PNG, atau WEBP."
    };
  }
  if (file.size > MAX_BYTES) {
    return {
      valid: false,
      alasan: "ukuran",
      pesan: "Ukuran melebihi 10 MB",
      subPesan: "Pilih gambar dengan ukuran maksimal 10 MB."
    };
  }
  return { valid: true };
}

// ---------------------------------------------------------------------------
// 2. Tampilkan Peringatan Format / Ukuran (Sequence Diagram s3 langkah 29)
// ---------------------------------------------------------------------------
function tampilkanPeringatanFormatUkuran(file, hasilValidasi) {
  const dropZone = $("drop");
  const stage = $("stage");
  const preview = $("pv");
  const invalidBox = $("invalidBox");
  const fileMeta = $("fileMeta");
  const fileWarn = $("fileWarn");
  const clearBtn = $("clr");
  const analyzeBtn = $("go");

  dropZone.style.display = "none";
  stage.classList.add("on", "invalid");

  if (hasilValidasi.alasan === "format") {
    preview.hidden = true;
    invalidBox.hidden = false;
  } else {
    // Ukuran > 10 MB: tetap tampilkan pratinjau dengan bingkai peringatan
    invalidBox.hidden = true;
    preview.hidden = false;
    preview.src = URL.createObjectURL(file);
  }

  if (fileMeta) {
    fileMeta.textContent = `${file.name} • ${formatUkuranMb(file.size)}`;
    fileMeta.hidden = false;
  }
  if (fileWarn) {
    fileWarn.textContent = hasilValidasi.pesan;
    fileWarn.hidden = false;
  }

  clearBtn.hidden = false;
  analyzeBtn.disabled = true;
}

// ---------------------------------------------------------------------------
// 3. Tampilkan Pratinjau Lokal (Sequence Diagram s3 langkah 6 & 10)
// ---------------------------------------------------------------------------
function tampilkanPratinjauLokal(file) {
  const dropZone = $("drop");
  const stage = $("stage");
  const preview = $("pv");
  const invalidBox = $("invalidBox");
  const fileMeta = $("fileMeta");
  const fileWarn = $("fileWarn");
  const clearBtn = $("clr");
  const analyzeBtn = $("go");

  dropZone.style.display = "none";
  stage.classList.remove("invalid");
  stage.classList.add("on");
  if (invalidBox) invalidBox.hidden = true;

  preview.hidden = false;
  preview.src = URL.createObjectURL(file);

  if (fileMeta) {
    fileMeta.textContent = `${file.name} • ${formatUkuranMb(file.size)}`;
    fileMeta.hidden = false;
  }
  if (fileWarn) {
    fileWarn.hidden = true;
    fileWarn.textContent = "";
  }

  clearBtn.hidden = false;
  analyzeBtn.disabled = false;
}

// ---------------------------------------------------------------------------
// 4. Pilih Gambar & Ganti Gambar (Sequence Diagram s3 langkah 4, 7, 8)
// ---------------------------------------------------------------------------
function pilihGambar(file) {
  sembunyikanErrorUmum();
  if (!file) return;

  const cek = validasiFormatDanUkuranFrontEnd(file);
  if (!cek.valid) {
    fileTerpilih = null;
    tampilkanPeringatanFormatUkuran(file, cek);
    return;
  }

  fileTerpilih = file;
  tampilkanPratinjauLokal(file);
}

function gantiGambar() {
  const fileInput = $("file");
  const dropZone = $("drop");
  const stage = $("stage");
  const fileMeta = $("fileMeta");
  const fileWarn = $("fileWarn");
  const statusBaca = $("statusBaca");
  const clearBtn = $("clr");
  const analyzeBtn = $("go");

  fileTerpilih = null;
  if (fileInput) fileInput.value = "";
  if (stage) stage.classList.remove("on", "invalid", "busy");
  if (dropZone) dropZone.style.display = "";
  if (fileMeta) fileMeta.hidden = true;
  if (fileWarn) fileWarn.hidden = true;
  if (statusBaca) statusBaca.hidden = true;
  if (clearBtn) clearBtn.hidden = true;
  if (analyzeBtn) {
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "Analisis gambar";
  }

  resetPanelHasil();
  sembunyikanErrorUmum();
  if (fileInput) fileInput.click();
}

// ---------------------------------------------------------------------------
// 5. Indikator Memuat & Panel Hasil (Sequence Diagram s3 langkah 12, 27, 28)
// ---------------------------------------------------------------------------
function tampilkanIndikatorMemuat(aktif) {
  const stage = $("stage");
  const analyzeBtn = $("go");
  const statusBaca = $("statusBaca");

  if (aktif) {
    if (stage) stage.classList.add("busy");
    if (analyzeBtn) {
      analyzeBtn.disabled = true;
      analyzeBtn.textContent = "Menganalisis…";
    }
    if (statusBaca) {
      statusBaca.textContent = "Sedang membaca gambar. Tunggu sebentar.";
      statusBaca.hidden = false;
    }
  } else {
    if (stage) stage.classList.remove("busy");
    if (analyzeBtn) {
      analyzeBtn.disabled = !fileTerpilih;
      analyzeBtn.textContent = "Analisis gambar";
    }
    if (statusBaca) {
      statusBaca.hidden = true;
    }
  }
}

function resetPanelHasil() {
  const res = $("res");
  const cam = $("cam");
  const emp = $("emp");
  const exBtn = $("ex");
  if (res) res.hidden = true;
  if (cam) cam.hidden = true;
  if (emp) emp.hidden = false;
  gradcamTerbuka = false;
  if (exBtn) exBtn.textContent = "Tampilkan Grad-CAM";
}

function tampilkanPanelHasil(data) {
  const isAi = data.label === "AI_ART" || data.labelTeks === "AI Art";
  const labelTeks = data.labelTeks || (isAi ? "AI Art" : "Human Art");
  const probHuman = Number(data.probHuman ?? (isAi ? 100 - data.confidence : data.confidence));
  const probAI = Number(data.probAI ?? (isAi ? data.confidence : 100 - data.confidence));
  const confidence = Number(data.confidence ?? Math.max(probHuman, probAI));

  $("vd").textContent = labelTeks;
  $("vd").className = "vd " + (isAi ? "a" : "h");
  $("cf").textContent = "Keyakinan model " + formatAngkaId(confidence) + "%";
  $("th").textContent = formatAngkaId(probHuman) + "%";
  $("ta").textContent = formatAngkaId(probAI) + "%";

  $("emp").hidden = true;
  $("res").hidden = false;

  requestAnimationFrame(() => {
    const humanLen = (probHuman / 100) * RING_LENGTH;
    const aiLen = (probAI / 100) * RING_LENGTH;
    if ($("rh") && $("ra")) {
      $("rh").setAttribute("stroke-dasharray", `${humanLen} 327`);
      $("ra").setAttribute("stroke-dasharray", `${aiLen} 327`);
      $("ra").setAttribute("stroke-dashoffset", -humanLen);
    }
    $("bh").style.width = `${probHuman}%`;
    $("ba").style.width = `${probAI}%`;
  });

  if (data.imageUrl) {
    $("io").src = data.imageUrl;
  } else if (fileTerpilih) {
    $("io").src = URL.createObjectURL(fileTerpilih);
  }
  if (data.heatmapUrl) {
    $("ih").src = data.heatmapUrl;
  }

  // Jika dipanggil dari Riwayat ("Lihat hasil"), langsung tampilkan pratinjau kiri & Grad-CAM
  if (data.dariRiwayat && data.imageUrl) {
    const dropZone = $("drop");
    const stage = $("stage");
    const preview = $("pv");
    const fileMeta = $("fileMeta");
    const clearBtn = $("clr");
    if (dropZone) dropZone.style.display = "none";
    if (stage) stage.classList.add("on");
    if (preview) {
      preview.hidden = false;
      preview.src = data.imageUrl;
    }
    if (fileMeta && data.fileName) {
      fileMeta.textContent = `${data.fileName} • ${data.waktuTeks || data.timestamp || ""}`;
      fileMeta.hidden = false;
    }
    if (clearBtn) clearBtn.hidden = false;
    gradcamTerbuka = true;
    $("cam").hidden = false;
    $("ex").textContent = "Sembunyikan Grad-CAM";
  } else {
    gradcamTerbuka = false;
    $("cam").hidden = true;
    $("ex").textContent = "Tampilkan Grad-CAM";
  }
}

function arahkanKeLogin(urlLogin) {
  window.location.href = urlLogin || "/masuk?pesan=sesi_berakhir";
}

function tampilkanErrorUmum(pesan) {
  const errEl = $("err");
  if (!errEl) return;
  errEl.textContent = pesan;
  errEl.hidden = false;
}

function sembunyikanErrorUmum() {
  const errEl = $("err");
  if (errEl) errEl.hidden = true;
}

// ---------------------------------------------------------------------------
// 6. Analisis Gambar ke Backend (Sequence Diagram s3 langkah 11–28)
// ---------------------------------------------------------------------------
async function analisisGambar() {
  if (!fileTerpilih) return;
  sembunyikanErrorUmum();
  tampilkanIndikatorMemuat(true);

  try {
    const formData = new FormData();
    formData.append("file", fileTerpilih);

    const resp = await fetch("/analisis", {
      method: "POST",
      headers: { "Accept": "application/json" },
      body: formData
    });
    let json = {};
    try {
      json = await resp.json();
    } catch (_) {}

    if (resp.status === 401) {
      arahkanKeLogin(json.redirect);
      return;
    }
    if (!resp.ok || json.ok === false) {
      tampilkanErrorUmum(json.error || "Analisis gagal. Silakan coba lagi.");
      return;
    }
    tampilkanPanelHasil(json);
  } catch (_) {
    tampilkanErrorUmum("Server tidak merespons. Pastikan aplikasi Flask berjalan.");
  } finally {
    tampilkanIndikatorMemuat(false);
  }
}

// ---------------------------------------------------------------------------
// 7. Alur Logout dengan Dialog Konfirmasi (Sequence Diagram s6 & Activity a6)
// ---------------------------------------------------------------------------
function tampilkanDialogKonfirmasiKeluar() {
  const modal = $("logoutModal");
  if (modal) modal.hidden = false;
}

function tutupDialogKonfirmasi() {
  const modal = $("logoutModal");
  if (modal) modal.hidden = true;
}

async function konfirmasiKeluar(pilihan) {
  if (pilihan !== "ya") {
    tutupDialogKonfirmasi();
    return;
  }
  try {
    const resp = await fetch("/logout", {
      method: "POST",
      headers: { "Accept": "application/json" }
    });
    const data = await resp.json().catch(() => ({}));
    arahkanKeLogin(data.redirect || "/masuk?pesan=sudah_keluar");
  } catch (_) {
    arahkanKeLogin("/masuk?pesan=sudah_keluar");
  }
}

// ---------------------------------------------------------------------------
// 8. Pengikatan Event DOM saat halaman dimuat
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const fileInput = $("file");
  const dropZone = $("drop");
  const clearBtn = $("clr");
  const analyzeBtn = $("go");
  const explainBtn = $("ex");
  const slider = $("sl");

  if (fileInput) {
    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files[0]) {
        pilihGambar(fileInput.files[0]);
      }
    });
  }

  if (dropZone) {
    const dropTitle = $("dropTitle");
    ["dragenter", "dragover"].forEach((evt) =>
      dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropZone.classList.add("over");
        if (dropTitle) dropTitle.textContent = "Lepaskan gambar di sini";
      })
    );
    ["dragleave", "drop"].forEach((evt) =>
      dropZone.addEventListener(evt, (e) => {
        e.preventDefault();
        dropZone.classList.remove("over");
        if (dropTitle) dropTitle.textContent = "Tarik gambar ke sini";
      })
    );
    dropZone.addEventListener("drop", (e) => {
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) pilihGambar(f);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", () => gantiGambar());
  }

  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", () => analisisGambar());
  }

  if (explainBtn) {
    explainBtn.addEventListener("click", () => {
      gradcamTerbuka = !gradcamTerbuka;
      $("cam").hidden = !gradcamTerbuka;
      explainBtn.textContent = gradcamTerbuka ? "Sembunyikan Grad-CAM" : "Tampilkan Grad-CAM";
      if (gradcamTerbuka) {
        $("cam").scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    });
  }

  if (slider) {
    slider.addEventListener("input", (e) => {
      const v = e.target.value;
      $("tp").style.clipPath = `inset(0 ${100 - v}% 0 0)`;
      $("b2").style.left = v + "%";
    });
  }

  // Tombol Keluar di navigasi
  document.querySelectorAll("[data-action='logout']").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      tampilkanDialogKonfirmasiKeluar();
    });
  });

  const btnKonfirmasiKeluar = $("btnKonfirmasiKeluar");
  const btnBatalKeluar = $("btnBatalKeluar");
  if (btnKonfirmasiKeluar) {
    btnKonfirmasiKeluar.addEventListener("click", () => konfirmasiKeluar("ya"));
  }
  if (btnBatalKeluar) {
    btnBatalKeluar.addEventListener("click", () => konfirmasiKeluar("batal"));
  }

  // Jika halaman dibuka lewat "Lihat hasil" dari Riwayat
  if (window.HASIL_AWAL_RIWAYAT) {
    tampilkanPanelHasil({ ...window.HASIL_AWAL_RIWAYAT, dariRiwayat: true });
    const studioSec = $("studio");
    if (studioSec) studioSec.scrollIntoView({ behavior: "smooth" });
  }
});

// Ekspos method sesuai nama di Sequence Diagram
window.ArtKuStudio = {
  pilihGambar,
  validasiFormatDanUkuranFrontEnd,
  tampilkanPratinjauLokal,
  tampilkanPeringatanFormatUkuran,
  gantiGambar,
  analisisGambar,
  tampilkanIndikatorMemuat,
  tampilkanPanelHasil,
  arahkanKeLogin,
  tampilkanDialogKonfirmasiKeluar,
  konfirmasiKeluar,
  tutupDialogKonfirmasi
};
