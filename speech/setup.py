"""Download the pinned, Apache-2.0 Azerbaijani checkpoint once, before serving."""
from .config import MODEL_ID, MODEL_REVISION, MODEL_DIR, MODEL_FILES, model_ready


def main():
    if model_ready():
        print('Azerbaycan dili modeli hazirdir.', flush=True)
        return
    from huggingface_hub import snapshot_download
    print('Azerbaycan dili modeli yuklenir (~1.6 GB). Ilk defe internet lazimdir.', flush=True)
    snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_dir=MODEL_DIR,
                      allow_patterns=[*MODEL_FILES, 'README.md'], max_workers=2)
    if not all((MODEL_DIR / name).is_file() for name in MODEL_FILES):
        raise RuntimeError('Model fayllari tam yuklenmedi; qurasdirmani yeniden basladin.')
    (MODEL_DIR / 'digiminds-revision.txt').write_text(MODEL_REVISION)
    print('Sesli SOS modeli hazirdir.', flush=True)


if __name__ == '__main__':
    main()
