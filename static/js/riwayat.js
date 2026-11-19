/* =========================================================
   riwayat.js
   Alur Riwayat Klasifikasi Art_ku
   Sesuai Sequence Diagram s4 & Activity Diagram a4:
   - pilihFilterUrutan(filter, urutan)
   - hapusRiwayat(id) -> tampilkanKonfirmasiHapus() -> konfirmasi (ya / batal)
   - lihatHasil(id) -> tampilkanPanelHasil()
   ========================================================= */

const $ = (id) => document.getElementById(id);

let idRiwayatAkanDihapus = null;
let filterSekarang = "semua";
let urutanSekarang = "terbaru";

const formatAngkaId = (n) =>
  Number(n || 0).toLocaleString("id-ID", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1
  });

function arahkanKeLogin(url) {
  window.location.href = url || "/masuk?pesan=sesi_berakhir";
}

// ---------------------------------------------------------------------------
// 1. Render Daftar Riwayat & Ringkasan (tampilkanRiwayat)
// ---------------------------------------------------------------------------
function tampilkanRiwayat(daftar, ringkasan) {
  if (ringkasan) {
    if ($("sumTotal")) $("sumTotal").textContent = ringkasan.total;
    if ($("sumAi")) $("sumAi").textContent = ringkasan.jumlahAIArt;
    if ($("sumHuman")) $("sumHuman").textContent = ringkasan.jumlahHumanArt;
  }

  const grid = $("riwayatGrid");
  const emptyState = $("riwayatKosong");
  if (!grid || !emptyState) return;

  if (!daftar || daftar.length === 0) {
    grid.innerHTML = "";
    grid.hidden = true;
    emptyState.hidden = false;
    return;
  }

  emptyState.hidden = true;
  grid.hidden = false;
  grid.innerHTML = daftar
    .map((item) => {
      const isAi = item.label === "AI_ART";
      const badgeClass = isAi ? "badge-ai" : "badge-human";
      const labelTeks = item.labelTeks || (isAi ? "AI Art" : "Human Art");
      return `
        <article class="hist-card" data-id="${item.id}">
          <div class="hist-thumb">
            <img src="${item.imageUrl}" alt="${item.fileName}" loading="lazy">
            <span class="hist-fname">${item.fileName}</span>
          </div>
          <div class="hist-body">
            <div class="hist-meta">
              <span class="hist-badge ${badgeClass}">${labelTeks}</span>
              <span class="hist-conf">Keyakinan ${formatAngkaId(item.confidence)}%</span>
            </div>
            <p class="hist-time">${item.waktuTeks || item.timestamp}</p>
            <div class="hist-actions">
              <a class="btn hist-view" href="/riwayat/${item.id}" data-id="${item.id}">Lihat hasil</a>
              <button type="button" class="btn g hist-del" data-del-id="${item.id}" data-del-name="${item.fileName}">Hapus</button>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

// ---------------------------------------------------------------------------
// 2. Filter & Urutan (Sequence Diagram s4 langkah 9–12)
// ---------------------------------------------------------------------------
async function pilihFilterUrutan(filter, urutan) {
  filterSekarang = filter || filterSekarang;
  urutanSekarang = urutan || urutanSekarang;

  // Perbarui tampilan tombol filter aktif
  document.querySelectorAll("[data-filter]").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-filter") === filterSekarang);
  });

  const url = `/riwayat?filter=${encodeURIComponent(filterSekarang)}&urutan=${encodeURIComponent(urutanSekarang)}`;
  try {
    const resp = await fetch(url, {
      headers: { "Accept": "application/json" }
    });
    const data = await resp.json().catch(() => ({}));
    if (resp.status === 401) {
      arahkanKeLogin(data.redirect);
      return;
    }
    if (resp.ok && data.ok) {
      tampilkanRiwayat(data.riwayat, data.ringkasan);
      window.history.replaceState({}, "", url);
    }
  } catch (_) {
    window.location.href = url;
  }
}

// ---------------------------------------------------------------------------
// 3. Hapus Riwayat + Dialog Konfirmasi (Sequence Diagram s4 langkah 13–23)
// ---------------------------------------------------------------------------
function hapusRiwayat(id, namaFile = "") {
  idRiwayatAkanDihapus = id;
  tampilkanKonfirmasiHapus(namaFile);
}

function tampilkanKonfirmasiHapus(namaFile = "") {
  const modal = $("deleteModal");
  const labelNama = $("deleteFileName");
  if (labelNama) {
    labelNama.textContent = namaFile ? `(${namaFile})` : "";
  }
  if (modal) modal.hidden = false;
}

function tutupKonfirmasiHapus() {
  const modal = $("deleteModal");
  if (modal) modal.hidden = true;
  idRiwayatAkanDihapus = null;
}

async function konfirmasiHapus(pilihan) {
  if (pilihan !== "ya" || !idRiwayatAkanDihapus) {
    // Pengguna membatalkan -> tampilkanRiwayat() (tanpa perubahan)
    tutupKonfirmasiHapus();
    return;
  }
  const id = idRiwayatAkanDihapus;
  tutupKonfirmasiHapus();

  try {
    const resp = await fetch(`/riwayat/${id}/hapus`, {
      method: "POST",
      headers: { "Accept": "application/json" }
    });
    const data = await resp.json().catch(() => ({}));
    if (resp.status === 401) {
      arahkanKeLogin(data.redirect);
      return;
    }
    if (resp.ok && data.ok) {
      // Ambil ulang daftar terfilter yang diperbarui
      await pilihFilterUrutan(filterSekarang, urutanSekarang);
    }
  } catch (_) {
    window.location.reload();
  }
}

// ---------------------------------------------------------------------------
// 4. Lihat Hasil (Sequence Diagram s4 langkah 24–27)
// ---------------------------------------------------------------------------
function lihatHasil(id) {
  window.location.href = `/riwayat/${id}`;
}

// ---------------------------------------------------------------------------
// 5. Dialog Konfirmasi Keluar (Logout)
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
// 6. Inisialisasi Event Listener
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  const root = document.body;
  filterSekarang = root.dataset.filterAktif || "semua";
  urutanSekarang = root.dataset.urutanAktif || "terbaru";

  // Tombol filter (Semua / AI Art / Human Art)
  document.querySelectorAll("[data-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      pilihFilterUrutan(btn.getAttribute("data-filter"), urutanSekarang);
    });
  });

  // Dropdown urutan
  const selectUrutan = $("selectUrutan");
  if (selectUrutan) {
    selectUrutan.addEventListener("change", () => {
      pilihFilterUrutan(filterSekarang, selectUrutan.value);
    });
  }

  // Delegasi klik tombol Hapus & Lihat hasil pada kartu riwayat
  const grid = $("riwayatGrid");
  if (grid) {
    grid.addEventListener("click", (e) => {
      const delBtn = e.target.closest("[data-del-id]");
      if (delBtn) {
        e.preventDefault();
        hapusRiwayat(delBtn.getAttribute("data-del-id"), delBtn.getAttribute("data-del-name"));
      }
    });
  }

  // Modal konfirmasi hapus
  const btnYaHapus = $("btnKonfirmasiHapus");
  const btnBatalHapus = $("btnBatalHapus");
  if (btnYaHapus) btnYaHapus.addEventListener("click", () => konfirmasiHapus("ya"));
  if (btnBatalHapus) btnBatalHapus.addEventListener("click", () => konfirmasiHapus("batal"));

  // Modal konfirmasi keluar
  document.querySelectorAll("[data-action='logout']").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      tampilkanDialogKonfirmasiKeluar();
    });
  });
  const btnKonfirmasiKeluar = $("btnKonfirmasiKeluar");
  const btnBatalKeluar = $("btnBatalKeluar");
  if (btnKonfirmasiKeluar) btnKonfirmasiKeluar.addEventListener("click", () => konfirmasiKeluar("ya"));
  if (btnBatalKeluar) btnBatalKeluar.addEventListener("click", () => konfirmasiKeluar("batal"));
});

window.ArtKuRiwayat = {
  pilihFilterUrutan,
  tampilkanRiwayat,
  hapusRiwayat,
  tampilkanKonfirmasiHapus,
  konfirmasiHapus,
  lihatHasil
};
