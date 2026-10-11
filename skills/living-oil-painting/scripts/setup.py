"""One-time setup: python deps + EDSR super-resolution models (-> scripts/models/) + fonts for the frame-dive template.

    python3 scripts/setup.py            # deps + models
    python3 scripts/setup.py --fonts    # also Oswald / Playfair Display (frame-dive titles)
"""
import os, subprocess, sys, tarfile, urllib.request, io, json

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, 'models')
URLS = {
    'EDSR_x2.pb': 'https://raw.githubusercontent.com/Saafke/EDSR_Tensorflow/master/models/EDSR_x2.pb',
    'EDSR_x4.pb': 'https://raw.githubusercontent.com/Saafke/EDSR_Tensorflow/master/models/EDSR_x4.pb',
}


def deps():
    need = []
    for mod, pkg in [('numpy', 'numpy'), ('PIL', 'pillow'), ('scipy', 'scipy')]:
        try:
            __import__(mod)
        except ImportError:
            need.append(pkg)
    try:
        import cv2
        if not hasattr(cv2, 'dnn_superres'):
            need.append('opencv-contrib-python-headless')
    except ImportError:
        need.append('opencv-contrib-python-headless')
    if need:
        print('pip install', *need)
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', *need])
    if subprocess.call(['ffmpeg', '-version'], stdout=subprocess.DEVNULL) != 0:
        print('!! ffmpeg not found: brew install ffmpeg / winget install ffmpeg / apt install ffmpeg')


def models():
    os.makedirs(MODELS, exist_ok=True)
    for name, url in URLS.items():
        dst = os.path.join(MODELS, name)
        if os.path.exists(dst) and os.path.getsize(dst) > 1e6:
            continue
        print('downloading', name)
        try:
            urllib.request.urlretrieve(url, dst)
        except Exception as e:
            print(f'  failed ({e}); fallback: git clone https://github.com/Saafke/EDSR_Tensorflow and copy models/{name} to {MODELS}')


def fonts(dst):
    os.makedirs(dst, exist_ok=True)
    for pkg in ['oswald', 'playfair-display']:
        meta = json.load(urllib.request.urlopen(f'https://registry.npmjs.org/@fontsource/{pkg}/latest'))
        data = urllib.request.urlopen(meta['dist']['tarball']).read()
        tarfile.open(fileobj=io.BytesIO(data)).extractall(os.path.join(dst, pkg))
        print('font', pkg, '->', dst)


if __name__ == '__main__':
    deps(); models()
    if '--fonts' in sys.argv:
        fonts(os.path.join(HERE, '..', 'templates', 'frame_dive', 'work', 'fonts'))
    print('setup done')
