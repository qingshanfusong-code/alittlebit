import cv2, sys, time
sr = cv2.dnn_superres.DnnSuperResImpl_create()
sr.readModel(sys.argv[1]); sr.setModel('edsr', 2)
for src, dst in zip(sys.argv[2::2], sys.argv[3::2]):
    t = time.time(); im = cv2.imread(src)
    out = sr.upsample(im); cv2.imwrite(dst, out, [cv2.IMWRITE_PNG_COMPRESSION, 3])
    print(src, im.shape, '->', out.shape, f'{time.time()-t:.1f}s', flush=True)
