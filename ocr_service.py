from pathlib import Path
try:
    import pytesseract
    from PIL import Image
    import subprocess
    subprocess.run(["tesseract", "--version"], capture_output=True, check=True)
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

def preprocess_for_ocr(image_path: str):
    import cv2
    from pathlib import Path

    img = cv2.imread(image_path)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    debug_path = Path(image_path).parent / ("debug_" + Path(image_path).name)
    try:
        cv2.imwrite(str(debug_path), enhanced)
    except Exception:
        pass

    return Image.fromarray(enhanced)


def run_ocr(image_path: str) -> str:
    if not OCR_AVAILABLE:
        return "OCR_NOT_AVAILABLE"

    try:
        pil_img = preprocess_for_ocr(image_path)
        if pil_img is None:
            return "OCR_ERROR"

        config = (
            "--psm 8 "
            "--oem 3 "
            "-c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        )

        raw = pytesseract.image_to_string(pil_img, config=config).strip()
        cleaned = "".join(c for c in raw if c.isalnum()).upper()

        if 3 <= len(cleaned) <= 10:
            return cleaned
        elif cleaned:
            return cleaned
        else:
            return "TIDAK_TERBACA"
    except Exception as e:
        print(f"[OCR Error] {e}")
        return "OCR_ERROR"
