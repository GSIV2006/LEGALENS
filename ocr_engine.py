import json
import os
import time
import tempfile
import re

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



def _targeted_declaration_ocr(image_path, base_results):
    """
    Run focused OCR around important declaration labels.

    The normal two-pass OCR can detect labels such as MRP while missing
    the nearby numeric value. This helper crops a region around those
    labels, enlarges it, and runs the existing OCR engine again.

    Only genuine OCR observations are added to the result set.
    """

    image = cv2.imread(image_path)

    if image is None:
        print("[OCR] Targeted OCR: unable to read image")
        return []

    height, width = image.shape[:2]

    declaration_patterns = [
        r"\bmrp\b",
        r"\bm\.?\s*r\.?\s*p\.?\b",
        r"\bmaximum\s+retail\s+price\b",
        r"\bnet\s*wt\.?\b",
        r"\bnet\s*weight\b",
        r"\bnet\s*(?:qty|quantity)\b",
        r"\bmfg\b",
        r"\bmanufactur",
        r"\bpacked\s+by\b",
        r"\bpacker\b",
        r"\bbest\s*before\b",
        r"\buse\s*by\b",
        r"\bexpiry\b",
        r"\bconsumer\s*care\b",
        r"\bcustomer\s*care\b",
    ]

    compiled_patterns = [
        re.compile(pattern, re.IGNORECASE)
        for pattern in declaration_patterns
    ]

    targeted_results = []

    for result in base_results:
        label_text = _normalize_text(result.get("text", ""))

        if not label_text:
            continue

        if not any(
            pattern.search(label_text)
            for pattern in compiled_patterns
        ):
            continue

        bbox = result.get("bbox", [])

        if not bbox or len(bbox) < 4:
            continue

        try:
            xs = [int(float(point[0])) for point in bbox]
            ys = [int(float(point[1])) for point in bbox]

            x1 = max(0, min(xs))
            y1 = max(0, min(ys))
            x2 = min(width, max(xs))
            y2 = min(height, max(ys))

            box_width = max(1, x2 - x1)
            box_height = max(1, y2 - y1)

            # Large enough margin to capture values printed beside,
            # above, or below the declaration label.
            margin_x = max(180, int(box_width * 1.8))
            margin_y = max(140, int(box_height * 2.5))

            crop_x1 = max(0, x1 - margin_x)
            crop_y1 = max(0, y1 - margin_y)
            crop_x2 = min(width, x2 + margin_x)
            crop_y2 = min(height, y2 + margin_y)

            crop = image[
                crop_y1:crop_y2,
                crop_x1:crop_x2,
            ]

            if crop.size == 0:
                continue

            crop_height, crop_width = crop.shape[:2]

            scale = 3.0

            enlarged = cv2.resize(
                crop,
                (
                    int(crop_width * scale),
                    int(crop_height * scale),
                ),
                interpolation=cv2.INTER_CUBIC,
            )

            gray = cv2.cvtColor(
                enlarged,
                cv2.COLOR_BGR2GRAY,
            )

            clahe = cv2.createCLAHE(
                clipLimit=2.5,
                tileGridSize=(8, 8),
            )

            enhanced = clahe.apply(gray)

            # Keep 3 channels for the PaddleOCR pipeline.
            enhanced = cv2.cvtColor(
                enhanced,
                cv2.COLOR_GRAY2BGR,
            )

            output_path = os.path.join(
                tempfile.gettempdir(),
                "legalens_targeted_declaration.jpg",
            )

            cv2.imwrite(
                output_path,
                enhanced,
                [
                    int(cv2.IMWRITE_JPEG_QUALITY),
                    95,
                ],
            )

            print(
                f"[OCR] Targeted crop for '{label_text}': "
                f"x={crop_x1}:{crop_x2}, "
                f"y={crop_y1}:{crop_y2}"
            )

            crop_results = _run_single_ocr(
                ocr_primary,
                output_path,
            )

            # Translate crop coordinates back into original-image
            # coordinates.
            for crop_result in crop_results:
                crop_bbox = crop_result.get("bbox", [])

                if not crop_bbox or len(crop_bbox) < 4:
                    continue

                restored_bbox = []

                for point in crop_bbox:
                    restored_bbox.append(
                        [
                            float(point[0]) / scale + crop_x1,
                            float(point[1]) / scale + crop_y1,
                        ]
                    )

                targeted_results.append(
                    {
                        "text": _normalize_text(
                            crop_result.get("text", "")
                        ),
                        "confidence": float(
                            crop_result.get(
                                "confidence",
                                0.0,
                            )
                        ),
                        "bbox": restored_bbox,
                        "ocr_verified": False,
                        "ocr_passes": 1,
                        "targeted": True,
                        "target_label": label_text,
                    }
                )

        except Exception as exc:
            print(
                f"[OCR] Targeted OCR failed for "
                f"'{label_text}': {exc}"
            )

    return targeted_results


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
    # TARGETED DECLARATION OCR
    # --------------------------------------------------------
    print("[OCR] Targeted declaration OCR")

    targeted_start = time.time()

    targeted_results = _targeted_declaration_ocr(
        image_path,
        primary_results + secondary_results,
    )

    print(
        "[OCR] Targeted OCR finished in "
        f"{time.time() - targeted_start:.2f}s "
        f"({len(targeted_results)} regions)"
    )

    # --------------------------------------------------------
    # RECONCILIATION
    # --------------------------------------------------------
    print("[OCR] Reconciling OCR passes")

    final_results = _reconcile_results(
        primary_results,
        secondary_results,
    )

    # Targeted OCR contains additional observations from
    # declaration regions that the full-image passes may miss.
    # Preserve them as additional evidence.
    final_results.extend(targeted_results)

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