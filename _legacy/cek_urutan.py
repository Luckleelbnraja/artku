"""Pakai: python cek_urutan.py "C:\\path\\test\\ai" "C:\\path\\test\\human" """
import glob
import sys

import timm
import torch
from PIL import Image
from torchvision import transforms as T

from config import ARCH, CLASSES, MEAN, MODEL_FILE, STD

if len(sys.argv) < 3:
    sys.exit('Pakai: python cek_urutan.py "folder_ai" "folder_human"')

ck = torch.load(MODEL_FILE, map_location="cpu")
print("tipe file:", type(ck), list(ck.keys())[:5] if isinstance(ck, dict) else "")
sd = ck
if isinstance(ck, dict):
    for k in ("model", "state_dict", "model_state_dict"):
        if k in ck:
            sd = ck[k]
            break
m = timm.create_model(ARCH, pretrained=False, num_classes=2)
m.load_state_dict(sd)
m.eval()
print("Bobot OK")

tf = T.Compose([T.Resize((224, 224)), T.ToTensor(), T.Normalize(MEAN, STD)])


def rata(folder):
    files = glob.glob(folder + "/*.jpg")[:20]
    with torch.no_grad():
        p = torch.stack([m(tf(Image.open(f).convert("RGB")).unsqueeze(0)).softmax(1)[0]
                         for f in files])
    return p.mean(0).tolist(), len(files)


(pa, na), (ph, nh) = rata(sys.argv[1]), rata(sys.argv[2])
print(f"Gambar AI    (n={na}): kelas0={pa[0]:.3f}  kelas1={pa[1]:.3f}")
print(f"Gambar HUMAN (n={nh}): kelas0={ph[0]:.3f}  kelas1={ph[1]:.3f}")

if pa[0] > pa[1] and ph[1] > ph[0]:
    benar = ["ai", "human"]
elif pa[1] > pa[0] and ph[0] > ph[1]:
    benar = ["human", "ai"]
else:
    sys.exit("Hasil tidak jelas. Kirim output ini ke chat.")
print("Urutan sebenarnya:", benar)
print("config.py SUDAH BENAR" if benar == CLASSES
      else f'UBAH config.py: CLASSES = {benar}')
