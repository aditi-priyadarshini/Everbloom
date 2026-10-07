from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
import warnings

def optimize_image(data):
    if not data or len(data)>8*1024*1024: raise ValueError('Images must be smaller than 8 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in ('JPEG','PNG','WEBP'): raise ValueError('Use JPEG, PNG or WebP images.')
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image=ImageOps.exif_transpose(image)
                image.thumbnail((2000,2000))
                image=image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
                output=BytesIO(); image.save(output,'WEBP',quality=85,method=4)
                return output.getvalue()
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:
        raise ValueError('This file is not a valid supported image.') from exc
