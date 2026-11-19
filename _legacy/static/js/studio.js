/* =========================================================
   studio.js
   Bagian "Studio analisis": unggah gambar, panggil backend
   Flask (/predict dan /explain), tampilkan hasil dan Grad-CAM.
   ========================================================= */

// ---------- Pengaturan ----------
const MAX_BYTES = 10 * 1024 * 1024;           // batas ukuran file: 10 MB
const ALLOWED_TYPES = /^image\/(jpeg|png|webp)$/;
const RING_LENGTH = 2 * Math.PI * 52;         // keliling cincin (r = 52)
const SERVER_DOWN_MSG = "Server tidak merespons. Pastikan aplikasi Flask masih berjalan di terminal.";

// ---------- Elemen ----------
const $ = (id) => document.getElementById(id);
const fileInput = $("file");
const dropZone = $("drop");
const stage = $("stage");
const preview = $("pv");
const analyzeBtn = $("go");
const explainBtn = $("ex");
const clearBtn = $("clr");

let currentFile = null; // file yang sedang dipilih

// Format angka Indonesia: 97.4 -> "97,4"
const formatNumber = (n) =>
  Number(n).toLocaleString("id-ID", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

// ---------- Pesan error ----------
function showError(message) {
  $("err").textContent = message;
  $("err").hidden = false;
}
function clearError() {
  $("err").hidden = true;
}

// ---------- Reset tampilan hasil ----------
function resetResult() {
  $("res").hidden = true;
  $("cam").hidden = true;
  $("int").hidden = true;
  $("emp").hidden = false;
  $("rh").setAttribute("stroke-dasharray", "0 327");
  $("ra").setAttribute("stroke-dasharray", "0 327");
  $("bh").style.width = "0";
  $("ba").style.width = "0";
}

// ---------- 1. Memilih file ----------
function takeFile(file) {
  clearError();
  resetResult();
  if (!file) return;

  if (!ALLOWED_TYPES.test(file.type)) {
    showError("Format harus JPG, PNG, atau WEBP.");
    analyzeBtn.disabled = true;
    return;
  }
  if (file.size > MAX_BYTES) {
    showError("Ukuran file maksimal 10 MB. Kecilkan gambar lalu coba lagi.");
    analyzeBtn.disabled = true;
    return;
  }

  currentFile = file;
  preview.src = URL.createObjectURL(file);
  stage.classList.add("on");
  dropZone.style.display = "none";
  clearBtn.hidden = false;
  analyzeBtn.disabled = false;
}

fileInput.addEventListener("change", () => takeFile(fileInput.files[0]));

// Drag and drop
["dragenter", "dragover"].forEach((name) =>
  dropZone.addEventListener(name, (e) => {
    e.preventDefault();
    dropZone.classList.add("over");
  })
);
["dragleave", "drop"].forEach((name) =>
  dropZone.addEventListener(name, (e) => {
    e.preventDefault();
    dropZone.classList.remove("over");
  })
);
dropZone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) {
    fileInput.files = e.dataTransfer.files;
    takeFile(file);
  }
});

// Tombol "Ganti gambar"
clearBtn.addEventListener("click", () => {
  fileInput.value = "";
  currentFile = null;
  stage.classList.remove("on");
  dropZone.style.display = "";
  clearBtn.hidden = true;
  analyzeBtn.disabled = true;
  resetResult();
  clearError();
});

// ---------- 2. Kirim gambar ke backend ----------
async function postImage(url) {
  const data = new FormData();
  data.append("image", currentFile); // nama field "image" dibaca oleh Flask
  const response = await fetch(url, { method: "POST", body: data });
  let json = {};
  try { json = await response.json(); } catch (e) { /* respons bukan JSON */ }
  return { ok: response.ok, json };
}

// ---------- 3. Tombol "Analisis gambar" ----------
function showResult(r) {
  const isAi = r.label === "AI-Generated";

  $("vd").textContent = r.label;
  $("vd").className = "vd " + (isAi ? "a" : "h");
  $("cf").textContent = "Keyakinan model " + formatNumber(r.confidence) + "%";
  $("th").textContent = formatNumber(r.human) + "%";
  $("ta").textContent = formatNumber(r.ai) + "%";
  $("emp").hidden = true;
  $("res").hidden = false;

  // Animasikan cincin dan bar setelah elemen tampil
  requestAnimationFrame(() => {
    const humanLength = (r.human / 100) * RING_LENGTH;
    $("rh").setAttribute("stroke-dasharray", humanLength + " 327");
    $("ra").setAttribute("stroke-dasharray", (r.ai / 100) * RING_LENGTH + " 327");
    $("ra").setAttribute("stroke-dashoffset", -humanLength);
    $("bh").style.width = r.human + "%";
    $("ba").style.width = r.ai + "%";
  });
}

analyzeBtn.addEventListener("click", async () => {
  clearError();
  resetResult();
  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Menganalisis...";
  stage.classList.add("busy"); // memunculkan garis pemindai

  try {
    const { ok, json } = await postImage("/predict");
    if (!ok) {
      showError(json.error || "Analisis gagal. Coba lagi.");
      return;
    }
    showResult(json);
  } catch (e) {
    showError(SERVER_DOWN_MSG);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Analisis gambar";
    stage.classList.remove("busy");
  }
});

// ---------- 4. Tombol "Tampilkan Grad-CAM" ----------
explainBtn.addEventListener("click", async () => {
  clearError();
  explainBtn.disabled = true;
  explainBtn.textContent = "Membuat Grad-CAM...";

  try {
    const { ok, json } = await postImage("/explain");
    if (!ok) {
      showError(json.error || "Grad-CAM gagal dibuat. Coba lagi.");
      return;
    }
    $("io").src = json.original;
    $("ih").src = json.overlay;

    // Teks penjelasan bersifat opsional (misalnya dari LLM)
    const text = json.interpretation || json.explanation;
    if (text) {
      $("it").textContent = text;
      $("int").hidden = false;
    }
    $("cam").hidden = false;
    $("cam").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    showError(SERVER_DOWN_MSG);
  } finally {
    explainBtn.disabled = false;
    explainBtn.textContent = "Tampilkan Grad-CAM";
  }
});

// ---------- 5. Slider perbandingan asli vs Grad-CAM ----------
$("sl").addEventListener("input", (e) => {
  const value = e.target.value;
  $("tp").style.clipPath = `inset(0 ${100 - value}% 0 0)`;
  $("b2").style.left = value + "%";
});
