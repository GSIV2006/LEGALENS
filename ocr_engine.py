import json
import os
import time
import tempfile

import cv2
from paddleocr import PaddleOCR


# ============================================================
# LEGALENS OCR ENGINE
# Two-pass OCR with image preprocessing + reconciliation
# ============================================================

ocr_primary = PaddleOCR(
    lang="en",
    text_detection_model_name="PP-OCRv6_small_det",
    text_recognition_model_name="PP-OCRv6_small_rec",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=True,
)

ocr_secondary = PaddleOCR(
    lang="en",
    text_detection_model_name="PP-OCRv6_small_det",
    text_recognition_model_name="PP-OCRv6_small_rec",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=True,
)


def _normalize_text(text):
    if not text:
        return ""

    text = str(text).strip()
    text = " ".join(text.split())

    return text


def _bbox_center(bbox):
    try:
        xs = [float(p[0]) for p in bbox]
        ys = [float(p[1]) for p in bbox]

        return (
            sum(xs) / len(xs),
            sum(ys) / len(ys),
        )
    except Exception:
        return 0.0, 0.0


def _bbox_distance(box_a, box_b):
    ax, ay = _bbox_center(box_a)
    bx, by = _bbox_center(box_b)

    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _run_single_ocr(engine, image_path):
    results = engine.predict(image_path)

    extracted = []

    for result in results:
        data = result.json

        if isinstance(data, str):
            data = json.loads(data)

        res = data.get("res", data)

        texts = res.get("rec_texts", [])
        scores = res.get("rec_scores", [])

        boxes = res.get(
            "rec_polys",
            res.get("rec_boxes", []),
        )

        for i, text in enumerate(texts):
            text = _normalize_text(text)

            if not text:
                continue

            confidence = (
                float(scores[i])
                if i < len(scores)
                else 0.0
            )

            if i < len(boxes):
                box = boxes[i]

                if hasattr(box, "tolist"):
                    bbox = box.tolist()
                else:
                    bbox = box
            else:
                bbox = []

            extracted.append(
                {
                    "text": text,
                    "confidence": round(
                        confidence,
                        4,
                    ),
                    "bbox": bbox,
                }
            )

    return extracted


def _preprocess_image(image_path):
    """
    Create a CPU-friendly normalized image for
    the second OCR pass.

    Keeps enough resolution for small packaging
    text while avoiding unnecessarily huge inputs.
    """

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(
            f"Unable to read image: {image_path}"
        )

    height, width = image.shape[:2]

    max_side = 2200

    scale = min(
        1.0,
        max_side / max(height, width),
    )

    if scale < 1.0:
        new_width = int(width * scale)
        new_height = int(height * scale)

        image = cv2.resize(
            image,
            (new_width, new_height),
            interpolation=cv2.INTER_AREA,
        )

    # Mild contrast normalization.
    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    enhanced = clahe.apply(gray)

    # Convert back to 3-channel image for OCR.
    enhanced = cv2.cvtColor(
        enhanced,
        cv2.COLOR_GRAY2BGR,
    )

    temp_dir = tempfile.gettempdir()

    output_path = os.path.join(
        temp_dir,
        "legalens_ocr_secondary.jpg",
    )

    cv2.imwrite(
        output_path,
        enhanced,
        [
            int(cv2.IMWRITE_JPEG_QUALITY),
            95,
        ],
    )

    return output_path


def _reconcile_results(primary, secondary):
    """
    Merge both OCR passes.

    When both passes produce matching text,
    confidence is increased.

    When they disagree, preserve both observations
    rather than inventing a value.
    """

    merged = []

    used_secondary = set()

    for p in primary:
        best_index = None
        best_score = None

        p_text = _normalize_text(
            p.get("text", "")
        )

        p_bbox = p.get("bbox", [])

        for index, s in enumerate(secondary):
            if index in used_secondary:
                continue

            s_text = _normalize_text(
                s.get("text", "")
            )

            if not s_text:
                continue

            distance = _bbox_distance(
                p_bbox,
                s.get("bbox", []),
            )

            p_lower = p_text.lower()
            s_lower = s_text.lower()

            text_match = (
                p_lower == s_lower
                or p_lower in s_lower
                or s_lower in p_lower
            )

            score = distance

            if text_match:
                score -= 1000

            if best_score is None or score < best_score:
                best_score = score
                best_index = index

        if best_index is not None:
            s = secondary[best_index]

            s_text = _normalize_text(
                s.get("text", "")
            )

            if (
                p_text.lower() == s_text.lower()
                or p_text.lower() in s_text.lower()
                or s_text.lower() in p_text.lower()
            ):
                combined_confidence = min(
                    0.99,
                    (
                        float(p.get("confidence", 0.0))
                        + float(s.get("confidence", 0.0))
                    )
                    / 2.0
                    + 0.08,
                )

                merged.append(
                    {
                        "text": p_text
                        if len(p_text) >= len(s_text)
                        else s_text,
                        "confidence": round(
                            combined_confidence,
                            4,
                        ),
                        "bbox": p_bbox
                        if p_bbox
                        else s.get("bbox", []),
                        "ocr_verified": True,
                        "ocr_passes": 2,
                    }
                )

                used_secondary.add(best_index)
                continue

        merged.append(
            {
                "text": p_text,
                "confidence": float(
                    p.get("confidence", 0.0)
                ),
                "bbox": p_bbox,
                "ocr_verified": False,
                "ocr_passes": 1,
            }
        )

    # Preserve secondary-only observations.
    for index, s in enumerate(secondary):
        if index in used_secondary:
            continue

        merged.append(
            {
                "text": _normalize_text(
                    s.get("text", "")
                ),
                "confidence": float(
                    s.get("confidence", 0.0)
                ),
                "bbox": s.get("bbox", []),
                "ocr_verified": False,
                "ocr_passes": 1,
            }
        )

    return merged


def run_ocr(image_path, output_json_path):
    print("=" * 60)
    print("[OCR] LEGALENS two-pass OCR")
    print(f"[OCR] Image: {image_path}")

    start_time = time.time()

    # --------------------------------------------------------
    # PASS 1 — Original image
    # --------------------------------------------------------
    print("[OCR] PASS 1: original image")

    primary_start = time.time()

    primary_results = _run_single_ocr(
        ocr_primary,
        image_path,
    )

    print(
        "[OCR] PASS 1 finished in "
        f"{time.time() - primary_start:.2f}s "
        f"({len(primary_results)} regions)"
    )

    # --------------------------------------------------------
    # PASS 2 — Preprocessed image
    # --------------------------------------------------------
    print("[OCR] Preparing PASS 2 image")

    secondary_image = _preprocess_image(
        image_path
    )

    print(
        f"[OCR] PASS 2 image: {secondary_image}"
    )

    secondary_start = time.time()

    secondary_results = _run_single_ocr(
        ocr_secondary,
        secondary_image,
    )

    print(
        "[OCR] PASS 2 finished in "
        f"{time.time() - secondary_start:.2f}s "
        f"({len(secondary_results)} regions)"
    )

    # --------------------------------------------------------
    # RECONCILIATION
    # --------------------------------------------------------
    print("[OCR] Reconciling OCR passes")

    final_results = _reconcile_results(
        primary_results,
        secondary_results,
    )

    verified_count = sum(
        1
        for item in final_results
        if item.get("ocr_verified")
    )

    print(
        "[OCR] Verified regions: "
        f"{verified_count}/{len(final_results)}"
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------
    with open(
        output_json_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            final_results,
            f,
            indent=4,
            ensure_ascii=False,
        )

    elapsed = time.time() - start_time

    print(
        "[OCR] Total OCR time: "
        f"{elapsed:.2f}s"
    )

    print("=" * 60)

    return final_results