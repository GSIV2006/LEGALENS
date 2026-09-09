import json
import time

from paddleocr import PaddleOCR


# CPU-friendly OCR configuration.
#
# PP-OCRv6 small is considerably lighter than the default
# PP-OCRv6 medium while retaining strong general OCR capability.
ocr = PaddleOCR(
    lang="en",
    text_detection_model_name="PP-OCRv6_small_det",
    text_recognition_model_name="PP-OCRv6_small_rec",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=True,
)


def run_ocr(image_path, output_json_path):
    print(f"[OCR] Starting: {image_path}")

    start_time = time.time()

    print("[OCR] Running PaddleOCR...")

    results = ocr.predict(image_path)

    elapsed = time.time() - start_time

    print(
        f"[OCR] PaddleOCR finished in "
        f"{elapsed:.2f}s"
    )

    extracted_data = []

    for result in results:
        data = result.json

        if isinstance(data, str):
            data = json.loads(data)

        # PaddleOCR 3.x result structure.
        res = data.get("res", data)

        texts = res.get("rec_texts", [])
        scores = res.get("rec_scores", [])

        boxes = res.get(
            "rec_polys",
            res.get("rec_boxes", []),
        )

        for i, text in enumerate(texts):
            if not text or not str(text).strip():
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

            extracted_data.append(
                {
                    "text": str(text).strip(),
                    "confidence": round(
                        confidence,
                        4,
                    ),
                    "bbox": bbox,
                }
            )

    with open(
        output_json_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            extracted_data,
            f,
            indent=4,
            ensure_ascii=False,
        )

    print(
        f"[OCR] Extracted "
        f"{len(extracted_data)} text regions"
    )

    return extracted_data