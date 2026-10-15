from pathlib import Path
import OpenImageIO as oiio
ROOT=Path(__file__).resolve().parents[1]
import argparse,json
p=argparse.ArgumentParser();p.add_argument('name');args=p.parse_args()
image=oiio.ImageBuf(str(ROOT/'renders'/f'{args.name}.exr'))
assert image.read(),image.geterror()
preview=oiio.ImageBufAlgo.colorconvert(image,'linear','sRGB')
assert preview.write(str(ROOT/'renders'/f'{args.name}.png')),preview.geterror()
print('Saved preview')
