"""Face-similarity search against the local performer photo database.

Algorithm (mirrors volom/PornStarSimilarity):

1. Detect the largest face in a photo with YuNet (OpenCV DNN).
2. Embed that face with ArcFace (ResNet50-based ``w600k_r50``) -> 512-d vector.
3. Compare cosine similarity against a pre-computed embedding index of the
   local performer photo DB, returning the top-k performers.

Embeddings are computed once and cached to ``embedding_index.npz`` next to the
photo database, so repeat queries only embed the input photo.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np

from research.performers.database import PerformerDatabase

logger = logging.getLogger(__name__)

EMBED_DIM = 512
FACE_SIZE = 112


class FaceSimilarityEngine:
    """Embeds faces and returns the most similar performers from the local DB."""

    def __init__(self, db: PerformerDatabase) -> None:
        self.db = db
        self._lock = threading.Lock()
        self._detector: Any = None  # cv2.FaceDetectorYN
        self._recognizer: Any = None  # onnxruntime session
        self._emb: np.ndarray | None = None  # (N, 512) L2-normalized
        self._emb_names: list[str] = []
        self._index_versions: dict[str, int] = {}

    # ------------------------------------------------------------------
    # lazy model load
    # ------------------------------------------------------------------

    @property
    def detector(self):
        if self._detector is None:
            import cv2

            model = self._model_path("yunet.onnx")
            self._detector = cv2.FaceDetectorYN.create(str(model), "", (640, 640))
        return self._detector

    @property
    def recognizer(self):
        if self._recognizer is None:
            import onnxruntime as ort

            model = self._model_path("w600k_r50.onnx")
            self._recognizer = ort.InferenceSession(
                str(model), providers=["CPUExecutionProvider"]
            )
        return self._recognizer

    def _model_path(self, name: str) -> Path:
        p = Path(self.db.config.data_dir) / "models" / name
        if not p.exists():
            raise FileNotFoundError(
                f"Face model not found: {p}\n"
                "Run: pip install -e '.[performers]' and ensure models are present."
            )
        return p

    # ------------------------------------------------------------------
    # embedding index
    # ------------------------------------------------------------------

    def _cached_index_path(self) -> Path:
        return Path(self.db.config.data_dir) / "embedding_index.npz"

    def requires_build(self) -> bool:
        p = self._cached_index_path()
        return not p.exists()

    def build_index(self, force: bool = False) -> None:
        """Embed every performer photo with a face and cache the matrix."""
        cache = self._cached_index_path()
        if not force and cache.exists():
            return

        photos = sorted(self.db.names_with_photos())
        if not photos:
            raise RuntimeError("No performer photos found to index.")

        names: list[str] = []
        vectors: list[np.ndarray] = []
        failed = 0
        for i, name in enumerate(photos):
            rec = self.db.get(name)
            if rec is None or not rec.photo:
                continue
            path = self.db.photo_path(rec.photo)
            if path is None:
                continue
            try:
                vec = self.embed_image(path)
                if vec is not None:
                    names.append(name)
                    vectors.append(vec)
                else:
                    failed += 1
            except Exception:  # noqa: BLE001
                failed += 1
            if i % 100 == 0 and i:
                logger.info("indexed %d/%d photos", i, len(photos))

        if not vectors:
            raise RuntimeError("No faces could be detected in the photo database.")

        matrix = np.vstack(vectors).astype(np.float32)
        matrix = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-12)
        try:
            Path(cache).parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(cache, names=np.array(names), embeddings=matrix)
        except Exception:
            logger.debug("Failed to save embedding index", exc_info=True)
        logger.info("Built face index for %d performers (%d no-face skipped)", len(names), failed)

    def _ensure_index(self) -> None:
        cache = self._cached_index_path()
        if not cache.exists():
            with self._lock:
                if not cache.exists():
                    self.build_index()
        if self._emb is None or not cache.exists():
            with self._lock:
                data = np.load(cache, allow_pickle=False)
                self._emb = data["embeddings"]
                self._emb_names = [str(n) for n in data["names"]]

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def embed_image(self, image_path: Path, max_faces: int = 1) -> np.ndarray | None:
        """Detect up to max_faces faces and return the first embedding, or None."""
        import cv2

        img = cv2.imread(str(image_path))
        if img is None:
            return None
        faces = self._detect_faces(img)
        if not faces:
            return None
        # prefer highest confidence
        faces.sort(key=lambda f: float(f[14]), reverse=True)
        boxes = [f[:4].astype(int) for f in faces[:max_faces]]
        embed = self._embed_boxes(img, boxes)
        return embed[0] if len(embed) else None

    def search(self, image_path: Path, top_k: int | None = None) -> list[dict[str, Any]]:
        """Return top-k performers most similar to the face in ``image_path``."""
        self._ensure_index()
        if top_k is None:
            top_k = self.db.config.top_k

        query = self.embed_image(image_path)
        if query is None:
            return []

        q = query.reshape(1, -1)
        sim = self._emb @ q.T  # (N, 1)
        sim = sim.ravel()

        order = np.argsort(-sim)
        results: list[dict[str, Any]] = []
        for idx in order:
            if len(results) >= top_k:
                break
            score = float(sim[idx])
            if score < self.db.config.min_similarity:
                break
            name = self._emb_names[idx]
            rec = self.db.get(name)
            if rec is None:
                continue
            results.append(
                {
                    "name": rec.name,
                    "score": round(score, 4),
                    "similarity": round(score, 4),
                    "photo": rec.photo,
                    "videos": rec.videos,
                    "views": rec.views,
                    "url": rec.url,
                    "gender": rec.gender,
                }
            )
        return results

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _detect_faces(self, img: np.ndarray) -> list[Any]:
        h, w = img.shape[:2]
        det = self.detector
        det.setInputSize((w, h))
        _result, faces = det.detect(img)
        if faces is None:
            return []
        return [f for f in faces]

    def _embed_boxes(self, img: np.ndarray, boxes: list[list[int]]) -> list[np.ndarray]:
        import cv2

        rec = self.recognizer
        input_name = rec.get_inputs()[0].name
        outs: list[np.ndarray] = []

        for (x, y, bw, bh) in boxes:
            x, y = max(0, int(x)), max(0, int(y))
            face = img[y : y + int(bh), x : x + int(bw)]
            if face.size == 0:
                continue
            im = cv2.resize(face, (FACE_SIZE, FACE_SIZE))
            im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
            im = (im.astype(np.float32) - 127.5) / 127.5
            im = np.transpose(im[None], (0, 3, 1, 2)).astype(np.float32)
            out = rec.run(None, {input_name: im})[0]
            v = np.asarray(out).reshape(-1)
            norm = np.linalg.norm(v)
            if norm > 0:
                v = v / norm
            outs.append(v.astype(np.float32))
        return outs


_engine: FaceSimilarityEngine | None = None
_engine_lock = threading.Lock()


def get_face_engine(db: PerformerDatabase) -> FaceSimilarityEngine:
    """Return the process-wide face-similarity engine for ``db``."""
    global _engine
    if _engine is None or _engine.db is not db:
        with _engine_lock:
            if _engine is None or _engine.db is not db:
                _engine = FaceSimilarityEngine(db)
    return _engine