"""Semua pengaturan model di satu tempat."""

ARCH = "swin_base_patch4_window7_224"
MODEL_FILE = "B_no_aug_seed42.pt"        # ganti ke "A_baseline_seed42.pt" untuk pindah model

# Urutan kelas = urutan output model. ImageFolder mengurutkan alfabet: ai=0, human=1.
# Kalau cek_urutan.py menunjukkan terbalik, cukup balik jadi ["human", "ai"].
CLASSES = ["human", "ai"]
LABELS = {"ai": "AI-Generated", "human": "Human Art"}

MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)

MATCH_TRAINING = True    # meniru data latih: resize 256 lalu JPEG, baru 224
JPEG_QUALITY = 90        # tebakan, bukan nilai asli dataset
