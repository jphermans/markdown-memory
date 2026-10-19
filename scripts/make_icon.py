from PIL import Image, ImageDraw
import os

S = 4  # supersampling factor
W = 256 * S
dark = (23, 42, 69)
accent = (240, 173, 78)
white = (248, 250, 252)
soft = (203, 213, 225)

img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Rounded-square background
d.rounded_rectangle([0, 0, W - 1, W - 1], radius=56 * S, fill=dark + (255,))

# Note card with folded corner
card_l, card_t, card_r, card_b = 52 * S, 44 * S, 204 * S, 212 * S
fold = 34 * S
d.polygon(
    [(card_l, card_t), (card_r - fold, card_t), (card_r, card_t + fold), (card_r, card_b), (card_l, card_b)],
    fill=white + (255,),
)
d.polygon(
    [(card_r - fold, card_t), (card_r - fold, card_t + fold), (card_r, card_t + fold)],
    fill=soft + (255,),
)

# Text lines on the card
lines = [(78, 86, 86), (78, 112, 86), (78, 138, 54)]
for i, (lx, ly, width) in enumerate(lines):
    x0, y0 = lx * S, ly * S
    x1, y1 = x0 + width * S, y0 + 12 * S
    col = accent + (255,) if i == 0 else (100, 116, 139) + (255,)
    d.rounded_rectangle([x0, y0, x1, y1], radius=6 * S, fill=col)

# Magnifier badge (semantic recall hint)
mx, my, mr = 176, 168, 26
cx, cy, cr = mx * S, my * S, mr * S
d.ellipse(
    [cx - cr, cy - cr, cx + cr, cy + cr],
    fill=(49, 130, 206) + (255,),
    outline=white + (255,),
    width=5 * S,
)
d.line(
    [cx + cr * 0.72, cy + cr * 0.72, cx + cr * 1.45, cy + cr * 1.45],
    fill=white + (255,),
    width=10 * S,
)

img = img.resize((256, 256), Image.LANCZOS)
out = "/a0/usr/plugins/markdown_memory/webui/thumbnail.png"
img.save(out, "PNG", optimize=True)
size = os.path.getsize(out)
print("thumbnail.png bytes:", size, "(limit 20480)", "OK" if size <= 20480 else "TOO BIG")
