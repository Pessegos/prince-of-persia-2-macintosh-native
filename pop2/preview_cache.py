"""Disposable, non-executable local caches for developer preview artwork."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
from zipfile import BadZipFile, ZipFile, ZIP_STORED

from PIL import Image

from pop2.paths import ASSET_DIR


def preview_fingerprint(directory=ASSET_DIR, code_directory=None):
    code_directory = Path(code_directory or Path(__file__).parent)
    digest = hashlib.sha256(b'pop2-developer-preview-1')
    for root, patterns in ((Path(directory), ('*.rsrc', '*.json')),
                           (code_directory, ('*.py',))):
        for path in sorted({path for pattern in patterns for path in root.glob(pattern)}):
            digest.update(path.name.encode('utf-8'))
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def read_preview(path, fingerprint):
    try:
        with ZipFile(path) as archive:
            info = archive.getinfo('manifest.json')
            if info.file_size > 65536:
                return None
            manifest = json.loads(archive.read(info))
            if manifest['schema'] != 1 or manifest['fingerprint'] != fingerprint:
                return None
            entries = manifest['images']
            if not isinstance(entries, list) or len(entries) > 128:
                return None
            images, total = {}, 0
            for index, entry in enumerate(entries):
                width, height = entry['size']
                if (type(width) is not int or type(height) is not int
                        or not 0 < width <= 8192 or not 0 < height <= 8192):
                    return None
                count = width * height * 3
                total += count
                info = archive.getinfo(f'{index}.rgb')
                if total > 128 * 1024 * 1024 or info.file_size != count:
                    return None
                images[entry['key']] = Image.frombytes('RGB', (width, height), archive.read(info))
            return manifest['metadata'], images
    except (OSError, BadZipFile, ValueError, KeyError, TypeError, OverflowError, RuntimeError):
        return None


def write_preview(path, fingerprint, metadata, images):
    path = Path(path)
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.preview-', delete=False) as stream:
            temporary = Path(stream.name)
        entries = [{'key': key, 'size': image.size} for key, image in images.items()]
        manifest = dict(schema=1, fingerprint=fingerprint, metadata=metadata, images=entries)
        with ZipFile(temporary, 'w', compression=ZIP_STORED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, separators=(',', ':')))
            for index, image in enumerate(images.values()):
                archive.writestr(f'{index}.rgb', image.convert('RGB').tobytes())
        os.replace(temporary, path)
    except OSError:
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
