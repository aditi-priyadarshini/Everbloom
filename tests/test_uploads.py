from io import BytesIO
from PIL import Image
import pytest
from services.uploads import optimize_image

def test_image_normalization():
    data=BytesIO(); Image.new('RGB',(3000,1000)).save(data,'PNG')
    result=optimize_image(data.getvalue())
    with Image.open(BytesIO(result)) as image:
        assert image.format=='WEBP' and image.width==2000

@pytest.mark.parametrize('data',[b'<svg onload=alert(1)>',b'not an image',b'x'*(8*1024*1024+1)])
def test_invalid_upload(data):
    with pytest.raises(ValueError): optimize_image(data)
