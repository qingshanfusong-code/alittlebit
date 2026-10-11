"""Font discovery by *role* so specs stay portable across macOS / Windows / Linux.

Roles: sans, sans_bold, light, thin, serif, serif_bold, condensed, script, mono,
       cjk_sans, cjk_bold, cjk_serif, cjk_brush, cjk_hand
A spec may also give a font file path or a family/file-name fragment ("Bodoni", "msyh").
"""
import glob
import os
import re
import sys

from PIL import ImageFont

FONT_DIRS = [
    "~/Library/Fonts", "/Library/Fonts", "/System/Library/Fonts", "/System/Library/Fonts/Supplemental",
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font*",  # macOS downloadable fonts (PingFang, Songti...)
    "C:/Windows/Fonts", "~/AppData/Local/Microsoft/Windows/Fonts",
    "/usr/share/fonts", "/usr/local/share/fonts", "~/.fonts", "~/.local/share/fonts",
]

# candidate file-name fragments, best first (case-insensitive, matched against file stem)
ROLES = {
    "sans": ["Inter-SemiBold", "HelveticaNeue", "Helvetica", "Arial", "SF-Pro", "Roboto-Medium",
             "LiberationSans-Regular", "DejaVuSans", "FreeSans"],
    "sans_bold": ["Inter-Black", "InterDisplay-Black", "Inter-ExtraBold", "Helvetica-Bold", "Arial Black", "ariblk",
                  "Arial Bold", "arialbd", "Roboto-Black", "LiberationSans-Bold", "DejaVuSans-Bold", "FreeSansBold"],
    "light": ["InterDisplay-Light", "Inter-Light", "HelveticaNeue-Light", "Avenir-Light", "Montserrat-Light",
              "Lato-Light", "Roboto-Light", "SourceSans3-Light", "LiberationSans-Regular", "DejaVuSans"],
    "thin": ["InterDisplay-Thin", "Inter-Thin", "InterDisplay-ExtraLight", "HelveticaNeue-Thin", "Avenir-Light",
             "Montserrat-Thin", "Roboto-Thin", "Lato-Hairline", "LiberationSans-Regular", "DejaVuSans-ExtraLight"],
    "serif": ["Didot", "Bodoni 72", "BodoniModa", "PlayfairDisplay-Regular", "Baskerville", "Georgia",
              "Times New Roman", "times", "Caladea-Regular", "LiberationSerif-Regular", "DejaVuSerif", "FreeSerif"],
    "serif_bold": ["Didot-Bold", "Bodoni 72 Bold", "PlayfairDisplay-Black", "PlayfairDisplay-Bold",
                   "Baskerville-Bold", "Georgia Bold", "georgiab", "timesbd", "Caladea-Bold",
                   "LiberationSerif-Bold", "DejaVuSerif-Bold", "FreeSerifBold"],
    "condensed": ["BebasNeue", "Anton", "Oswald-Bold", "LeagueGothic", "Impact", "AvenirNextCondensed-Heavy",
                  "HelveticaNeue-CondensedBlack", "RobotoCondensed-Bold", "LiberationSansNarrow-Bold",
                  "DejaVuSansCondensed-Bold"],
    "script": ["SnellRoundhand", "GreatVibes", "Allura", "AlexBrush", "Pinyon", "DancingScript", "Pacifico",
               "Zapfino", "BRUSHSCI", "Brush Script", "SavoyeLET", "Lobster"],
    "mono": ["JetBrainsMono", "SFMono", "Menlo", "Consolas", "CourierPrime", "LiberationMono-Regular",
             "DejaVuSansMono", "FreeMono"],
    "cjk_sans": ["PingFang", "Hiragino Sans GB", "SourceHanSansSC-Regular", "NotoSansCJKsc-Regular",
                 "NotoSansSC-Regular", "NotoSansCJK-Regular", "msyh", "Microsoft YaHei", "STHeiti", "simhei",
                 "wqy-microhei", "wqy-zenhei", "ipag", "unifont"],
    "cjk_bold": ["PingFang", "SourceHanSansSC-Heavy", "SourceHanSansSC-Bold", "NotoSansCJKsc-Black",
                 "NotoSansCJKsc-Bold", "NotoSansSC-Black", "NotoSansSC-Bold", "msyhbd", "simhei", "STHeiti",
                 "wqy-zenhei", "ipag"],
    "cjk_serif": ["Songti", "STSong", "SourceHanSerifSC", "NotoSerifCJKsc", "NotoSerifSC", "simsun", "STZhongsong",
                  "FangSong", "simfang"],
    "cjk_brush": ["STXingkai", "Xingkai", "ZhiMangXing", "LiuJianMaoCao", "MaShanZheng", "STKaiti", "Kaiti",
                  "simkai", "LXGWWenKai"],
    "cjk_hand": ["LXGWWenKai", "ZCOOLKuaiLe", "MaShanZheng", "STKaiti", "Kaiti", "simkai"],
}
CJK_FALLBACK = {"serif": "cjk_serif", "serif_bold": "cjk_serif", "script": "cjk_brush", "thin": "cjk_sans",
                "light": "cjk_sans",
                "sans_bold": "cjk_bold", "condensed": "cjk_bold"}
ROLE_FALLBACK = {"cjk_serif": "cjk_sans", "cjk_brush": "cjk_serif", "cjk_hand": "cjk_brush", "cjk_bold": "cjk_sans",
                 "condensed": "sans_bold", "script": "serif", "thin": "light", "light": "sans", "serif_bold": "serif",
                 "sans_bold": "sans", "mono": "sans", "serif": "sans"}

_CJK_RE = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")


def has_cjk(text):
    return bool(_CJK_RE.search(text or ""))


class FontBook:
    def __init__(self, extra_dirs=(), overrides=None):
        self.files = []
        dirs = list(extra_dirs) + FONT_DIRS
        expanded = []
        for d in dirs:
            d = os.path.expanduser(d)
            expanded += sorted(glob.glob(d)) if any(c in d for c in "*?[") else [d]
        for d in expanded:
            if os.path.isdir(d):
                for ext in ("ttf", "otf", "ttc", "TTF", "OTF", "TTC"):
                    self.files += glob.glob(os.path.join(d, "**", f"*.{ext}"), recursive=True)
        self.files = sorted(set(self.files))
        self.overrides = overrides or {}
        self._cache = {}
        self._role_cache = {}
        self.synthetic = {}  # role -> dict of synthetic tweaks when the real style is missing

    def _find(self, frag):
        f = frag.lower().replace(" ", "")
        best = None
        for p in self.files:
            stem = os.path.splitext(os.path.basename(p))[0].lower().replace(" ", "")
            if stem == f:
                return p
            if f in stem and (best is None or len(stem) < len(os.path.basename(best))):
                best = p
        return best

    def resolve(self, name, text=""):
        """Return (path, synthetic_tweaks) for a role / path / fragment."""
        name = name or "sans"
        key = (name, has_cjk(text))
        if key in self._role_cache:
            return self._role_cache[key]
        res = self._resolve(name, has_cjk(text))
        self._role_cache[key] = res
        return res

    def _resolve(self, name, cjk):
        if name in self.overrides:
            name = self.overrides[name]
        if os.path.isfile(os.path.expanduser(str(name))):
            return os.path.expanduser(name), {}
        tweaks = {}
        role = name if name in ROLES else None
        if role is None:
            p = self._find(name)
            if p:
                return p, {}
            role = "cjk_sans" if cjk else "sans"
        if cjk and not role.startswith("cjk"):
            role = CJK_FALLBACK.get(role, "cjk_sans")
        seen = set()
        r = role
        while r and r not in seen:
            seen.add(r)
            if r in self.overrides and os.path.isfile(os.path.expanduser(self.overrides[r])):
                return os.path.expanduser(self.overrides[r]), tweaks
            for frag in ROLES.get(r, []):
                p = self._find(frag)
                if p:
                    if r != role:
                        tweaks = synthetic_for(role)
                    return p, tweaks
            r = ROLE_FALLBACK.get(r)
        # last resort: PIL default
        return None, synthetic_for(role)

    def font(self, name, size, text=""):
        path, tweaks = self.resolve(name, text)
        key = (path, int(size))
        if key not in self._cache:
            if path is None:
                self._cache[key] = ImageFont.load_default(size=int(size))
            else:
                idx = 0
                try:
                    self._cache[key] = ImageFont.truetype(path, int(size), index=idx)
                except OSError:
                    self._cache[key] = ImageFont.load_default(size=int(size))
        return self._cache[key], tweaks

    def report(self):
        lines = []
        for role in ROLES:
            p, tw = self.resolve(role, "字" if role.startswith("cjk") else "")
            lines.append(f"{role:11s} -> {os.path.basename(p) if p else 'PIL default'}"
                         + (f"   (synthetic: {tw})" if tw else ""))
        return "\n".join(lines)


def synthetic_for(role):
    """When the ideal face is missing, fake its silhouette so layouts still read right."""
    return {
        "condensed": {"scale_x": 0.62},
        "script": {"skew": 0.22},
        "thin": {},
        "cjk_brush": {"skew": 0.08},
    }.get(role, {})


if __name__ == "__main__":
    fb = FontBook(sys.argv[1:])
    print(f"{len(fb.files)} font files indexed")
    print(fb.report())
