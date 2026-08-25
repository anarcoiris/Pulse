script = """
import re

with open("core/visual_inference.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace VisualInspectionReport dataclass to include radar field
old_dc = '''@dataclass
class VisualInspectionReport:
    \"\"\"Complete summary of the 5-pass visual inspection gate.\"\"\"
    passed: bool
    visual_score: float  # 0 to 100
    violations_count: int
    violations: List[VisualViolation]
    courtyards: List[Dict[str, Any]]
    stats: Dict[str, Any] = field(default_factory=dict)'''

new_dc = '''@dataclass
class VisualInspectionReport:
    \"\"\"Complete summary of the 9-pass visual & DFM inspection gate.\"\"\"
    passed: bool
    visual_score: float  # 0 to 100
    violations_count: int
    violations: List[VisualViolation]
    courtyards: List[Dict[str, Any]]
    radar: Dict[str, float] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)'''

if old_dc in content:
    content = content.replace(old_dc, new_dc)
    print("Replaced VisualInspectionReport dataclass.")
else:
    print("Warning: old_dc not found.")

with open("core/visual_inference.py", "w", encoding="utf-8") as f:
    f.write(content)
"""

with open("scripts/patch_vis_dc.py", "w", encoding="utf-8") as f:
    f.write(script)

