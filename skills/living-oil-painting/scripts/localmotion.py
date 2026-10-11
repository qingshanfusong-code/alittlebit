"""Find motion *inside* a painting: dense flow between two frames minus the global camera move."""
import sys, cv2, numpy as np
a_path, b_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
A = cv2.imread(a_path); B = cv2.imread(b_path)
s = 960 / A.shape[1]
A = cv2.resize(A, None, fx=s, fy=s, interpolation=cv2.INTER_AREA); B = cv2.resize(B, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
ga, gb = cv2.cvtColor(A, cv2.COLOR_BGR2GRAY), cv2.cvtColor(B, cv2.COLOR_BGR2GRAY)
flow = cv2.calcOpticalFlowFarneback(ga, gb, None, 0.5, 4, 21, 5, 7, 1.5, 0)
h, w = ga.shape
ys, xs = np.mgrid[8:h:16, 8:w:16]
src = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float32)
dst = src + flow[ys.ravel(), xs.ravel()]
M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=1.0)
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
pred = np.stack([M[0, 0] * xx + M[0, 1] * yy + M[0, 2] - xx, M[1, 0] * xx + M[1, 1] * yy + M[1, 2] - yy], -1)
res = flow - pred
mag = np.linalg.norm(res, axis=-1)
print(f'{a_path.split("/")[-1]}->{b_path.split("/")[-1]} global scale {np.hypot(M[0,0],M[1,0]):.4f} shift ({M[0,2]:.1f},{M[1,2]:.1f}) '
      f'residual mean {mag.mean():.2f}px p95 {np.percentile(mag,95):.2f}px max {mag.max():.1f}px  inliers {inl.mean():.2f}')
heat = cv2.applyColorMap(np.clip(mag / max(1.0, np.percentile(mag, 99)) * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
vis = cv2.addWeighted(A, 0.45, heat, 0.75, 0)
for y in range(12, h, 24):
    for x in range(12, w, 24):
        dx, dy = res[y, x] * 4
        if np.hypot(dx, dy) > 2:
            cv2.arrowedLine(vis, (x, y), (int(x + dx), int(y + dy)), (255, 255, 255), 1, tipLength=0.3)
cv2.imwrite(out, np.hstack([A, vis]))
