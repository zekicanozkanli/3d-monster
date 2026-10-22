"""Front-view landmarks traced from the user's supplied monster image.

Pixel coordinates use image origin at upper left, in the 1438 x 1094 image.
Depth, physical scale, and minimum feature sizes require user specifications.
These are sculpting guides, not exact engineering measurements.
"""

from pathlib import Path

REFERENCE_IMAGE = str(Path(__file__).resolve().parent / "references" / "monster-reference.png")
IMAGE_SIZE = (1438, 1094)

# Each head has its own mouth direction and asymmetric silhouette.
HEADS = [
    {"name": "Left_Low", "center_px": (220, 543), "radii_px": (151, 120),
     "mouth_center_px": (204, 566), "mouth_radii_px": (75, 44),
     "mouth_axis_px": (0.57, -0.82)},
    {"name": "Left_High", "center_px": (423, 196), "radii_px": (132, 121),
     "mouth_center_px": (430, 217), "mouth_radii_px": (75, 48),
     "mouth_axis_px": (0.94, -0.34)},
    {"name": "Center", "center_px": (748, 256), "radii_px": (139, 105),
     "mouth_center_px": (753, 297), "mouth_radii_px": (77, 39),
     "mouth_axis_px": (1.0, 0.0)},
    {"name": "Right_High", "center_px": (1056, 180), "radii_px": (134, 123),
     "mouth_center_px": (1068, 214), "mouth_radii_px": (68, 43),
     "mouth_axis_px": (0.98, 0.20)},
    {"name": "Right_Low", "center_px": (1280, 410), "radii_px": (122, 116),
     "mouth_center_px": (1296, 440), "mouth_radii_px": (70, 42),
     "mouth_axis_px": (0.74, 0.67)},
]

# Centerlines run from the torso junction toward each head.
NECK_PATHS_PX = {
    "Left_Low": [(675, 684), (514, 654), (377, 614), (289, 559)],
    "Left_High": [(682, 624), (579, 536), (504, 408), (459, 292)],
    "Center": [(737, 621), (737, 505), (733, 409), (737, 337)],
    "Right_High": [(792, 631), (901, 550), (997, 413), (1036, 284)],
    "Right_Low": [(807, 678), (969, 621), (1114, 546), (1208, 459)],
}

FOOT_CENTERS_PX = [(558, 956), (913, 954)]
TORSO_CENTER_PX = (742, 759)
SOLE_Y_PX = 1007

# Confirmed by the user. Values still requiring an answer remain unset.
PRINT_REQUIREMENTS = {
    "envelope_mm": (138, 30, 100),
    "exact_dimensions_mm": (138, 30, 100),
    "preserve_reference_proportions": False,
    "one_piece": True,
    "base": False,
    "supports_allowed": True,
    "process": "filament",
    "material": None,
    "nozzle_mm": None,
    "printer": None,
    "depth_and_back_inference_authorized": True,
    "teeth_recessed_inside_mouths": True,
}
