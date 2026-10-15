"""Neuronales Netz für Pfeilspitzen (YOLO → ONNX, trainiert mit tools/train_tips.py).

Liegt data/models/tips.onnx vor, wird es benutzt – sonst arbeitet die App wie bisher.
Läuft mit OpenCV-DNN (keine Zusatzpakete) oder, falls installiert, mit onnxruntime (schneller).
"""
import logging, os, time

import cv2
import numpy as np

from .config import DATA

log = logging.getLogger("uvicorn.error")
MODEL = os.environ.get("TIPNET", os.path.join(DATA, "models", "tips.onnx"))
CONF = float(os.environ.get("TIPNET_CONF", 0.35))
NMS_PX = 10.0


class TipNet:
    def __init__(self, path=MODEL):
        self.path, self.sess, self.net, self.size = path, None, None, 1280
        try:
            import onnxruntime as ort
            self.sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
            shp = self.sess.get_inputs()[0].shape
            self.size = int(shp[2]) if isinstance(shp[2], int) else 1280
            self.inp = self.sess.get_inputs()[0].name
            self.backend = "onnxruntime"
        except Exception:
            self.net = cv2.dnn.readNetFromONNX(path)
            self.backend = "opencv"
        self.ms = 0.0
        log.info("Pfeil-Netz geladen: %s (%s, %d px)", os.path.basename(path), self.backend, self.size)

    def __call__(self, img):
        """BGR-Bild → [(u, v, conf), …] in Bildpixeln."""
        t0 = time.time()
        h, w = img.shape[:2]
        s = self.size / max(w, h)
        nw, nh = int(round(w * s)), int(round(h * s))
        canvas = np.full((self.size, self.size, 3), 114, np.uint8)
        top, left = (self.size - nh) // 2, (self.size - nw) // 2
        canvas[top:top + nh, left:left + nw] = cv2.resize(img, (nw, nh))
        blob = cv2.dnn.blobFromImage(canvas, 1 / 255.0, swapRB=True)
        if self.sess is not None:
            out = self.sess.run(None, {self.inp: blob})[0]
        else:
            self.net.setInput(blob)
            out = self.net.forward()
        p = out[0].T if out.shape[1] < out.shape[2] else out[0]   # (N, 5): cx, cy, w, h, score
        p = p[p[:, 4] >= CONF]
        p = p[np.argsort(-p[:, 4])]
        tips = []
        for cx, cy, _, _, sc in p:
            u, v = (cx - left) / s, (cy - top) / s
            if all((u - a) ** 2 + (v - b) ** 2 > NMS_PX ** 2 for a, b, _ in tips):
                tips.append((float(u), float(v), float(sc)))
        self.ms = (time.time() - t0) * 1000
        return tips


_net = None


def get():
    """Modell einmal laden (None, wenn keins da oder defekt)."""
    global _net
    if _net is None and os.path.exists(MODEL):
        try:
            _net = TipNet(MODEL)
        except Exception as e:
            log.warning("Pfeil-Netz nicht ladbar (%s) – Erkennung ohne Netz", e)
            _net = False
    return _net or None
