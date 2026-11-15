from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_ID = 'hasan0v/whisper-turbo-az-ct2'
MODEL_REVISION = 'e41a2b4e276d27f3416ae975dbf0d90ca352a6d2'
MODEL_DIR = ROOT / 'data' / 'speech-model'
MODEL_FILES = ('config.json', 'model.bin', 'preprocessor_config.json', 'tokenizer.json', 'vocabulary.json')
MAX_SECONDS = 20
MAX_UPLOAD = 8 * 1024 * 1024


def model_ready():
    marker = MODEL_DIR / 'digiminds-revision.txt'
    return (marker.is_file() and marker.read_text().strip() == MODEL_REVISION
            and all((MODEL_DIR / name).is_file() for name in MODEL_FILES))
