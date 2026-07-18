# KiCad Output Audit & Improvement Plan

After a deep review of the generated [board.kicad_sch](file:///C:/Users/soyko/Documents/Pulse-main/output/pulselab_pcb/board.kicad_sch) and the generation pipeline ([schematic_generator.py](file:///C:/Users/soyko/Documents/Pulse-main/bridge/schematic_generator.py), [pcb_builder.py](file:///C:/Users/soyko/Documents/Pulse-main/bridge/pcb_builder.py), [pcb_layout.py](file:///C:/Users/soyko/Documents/Pulse-main/bridge/pcb_layout.py), [component_types.py](file:///C:/Users/soyko/Documents/Pulse-main/core/component_types.py)), here's what I found.

## Issues Found

### 1. Version Mismatch (The warning you saw)

> [!CAUTION]
> The schematic uses `(version 20231120)` (KiCad 8.0) and the PCB uses `(version 20240108)` (KiCad 8.x).  
> Your installed KiCad is **10.0.3**. KiCad 10 expects `(version 20241228)` for `.kicad_sch` and a newer version tag for `.kicad_pcb`.

| File | Current version | KiCad 10.0.3 expected |
|---|---|---|
| `schematic_generator.py:85` | `20231120` | `20241228` |
| `pcb_layout.py:1110` | `20240108` | `20241228` |

---

### 2. Schematic: Empty Symbol Stubs (Critical)

The `lib_symbols` section emits **placeholder stubs** with no actual pin definitions or graphical bodies:

```
(symbol "RF_Module:ESP32-S3-WROOM-1" (pin_numbers hide) (pin_names (offset 1.016) hide)
  (property "Reference" "U" ...)
  (property "Value" "Val" ...)
  ;; NO (symbol ... (pin ...) blocks!) — KiCad renders this as an empty box
)
```

KiCad **requires** real `(pin ...)` definitions inside `lib_symbols` for pins to appear and for ERC to function. The current stubs mean:
- No pin graphics are drawn on the schematic
- No electrical connections can be validated
- DRC/ERC will flag every component as "no pins"

---

### 3. Schematic: Flat Linear Layout (Your spatial concern)

All 24 components are placed on a **single horizontal line** at `y=50.0`, spaced 10.16mm apart (2× the grid scale). This stretches the schematic to ~283mm wide — off the page for A4. 

The schematic should instead group components by functional block:
- MCU in center
- I2C devices (SSD1306) near SDA/SCL pins
- SPI devices (PN532, CC1101) near MOSI/MISO/SCK pins
- D-Pad buttons grouped together
- Pull-up resistors near their buttons
- Decoupling caps near power pins

---

### 4. Footprint: ICs Use Generic Connectors Instead of Real Footprints

| Component | Current footprint | Should be |
|---|---|---|
| SSD1306 (OLED) | `Connector_PinHeader_2.54mm:PinHeader_1x04` | Module-specific or SSD1306 OLED footprint |
| PN532 (NFC) | `Connector_PinHeader_2.54mm:PinHeader_1x07` | `Package_SO:SOP-24` or NFC module breakout |
| CC1101 (Sub-GHz) | `Connector_PinHeader_2.54mm:PinHeader_1x08` | `Package_SO:TSSOP-20` or module footprint |
| ESP32-S3 | Falls back to `SOP16` in `_place_ic()` | `RF_Module:ESP32-S3-WROOM-1` (already in JSON but not honored by PCB builder) |

The root cause is in [pcb_builder.py](file:///C:/Users/soyko/Documents/Pulse-main/bridge/pcb_builder.py#L166-L196): The `footprint_id` attribute from the circuit JSON **is checked** (`getattr(c, 'footprint_id', None)`) but the `add_raw_footprint()` call often fails silently because the footprint library doesn't exist on disk as a `.kicad_mod` file — the generator writes inline pads only for known presets (0805 resistors, tactile switches, SOP packages).

---

### 5. Component Values: Raw Float Instead of Human-Readable

The schematic shows `"Value" "0.0"` for ICs/switches and `"Value" "1e-07"` for capacitors. These should be:
- `"ESP32-S3"` for the MCU (use the part name)
- `"100nF"` for 1e-7 F capacitors
- `"10µF"` for 1e-5 F
- `"10kΩ"` for 10000.0 Ω resistors

The `VALUE_FMT` dict in `component_types.py` already has formatters, but the schematic generator calls `str(c.value)` directly instead of using `_fmt_value()`.

---

### 6. Missing Wires in Schematic

The schematic only has **net labels floating near component positions** but **zero `(wire ...)` segments**. All connections are implicit through label matching. While KiCad technically supports this, it produces a schematic that looks like a random cloud of labels with no visible connectivity — useless for visual inspection.

---

### 7. `ESP32-S3` Maps to Wrong Symbol in `VALUE_SYMBOL_MAP`

In [component_types.py:48](file:///C:/Users/soyko/Documents/Pulse-main/core/component_types.py#L48):
```python
"ESP32-S3": "RF_Module:ESP32-WROOM-32",  # WRONG! Should be ESP32-S3-WROOM-1
```
This causes a mismatch between the symbol declared in the JSON (`RF_Module:ESP32-S3-WROOM-1`) and the fallback used when the schematic generator tries to resolve the lib_id.

---

## Phase 3: Spatial Layout & Size-Awareness (NEW)

> [!TIP]
> The current spatial mapping in `pcb_builder.py` is a highly rigid, dumb grid setup. Components are just pushed into `(col * 15mm, row * 15mm)`. This ignores sizes (a huge ESP32 footprint might collide with another element immediately if the cell size is only 15mm).

To fix the chaotic layout, we will build a **Hierarchical Island Packing Algorithm**:

1. **Size Estimation Dictionary**:
   We'll build a heuristic table for component dimensions inside `pcb_builder.py`:
   - `R`, `C`, `L` (0805): 2.5 x 1.5 mm
   - `MCU` (ESP32): 20 x 30 mm
   - `IC` (SOP8): 5 x 6 mm
   - Pin Headers: `N * 2.54` mm

2. **Topological Clustering (Islands)**:
   - Instead of placing components sequentially from an unstructured array, we'll traverse the circuit graph to build "Islands".
   - If a resistor or capacitor shares a net with an `IC` or `MCU`, it gets assigned to that IC's island.
   - The central IC is placed at `(0, 0)` within its local island coordinate space. Dependent passives are arranged in a ring or sub-grid closely hugging the central IC's bounding box.

3. **Dynamic Island Packing**:
   - Once all islands (e.g., "MCU Island", "I2C Sensor Island") have their local bounding boxes calculated, we use a dynamic grid to pack the entire board. Row heights and Column widths will expand flexibly to accommodate the largest island in that slot.

4. **Synchronized Schematic Topology**:
   - `schematic_generator.py` will inherit this same Island logic, visually grouping dependencies together on the schematic diagram just like they appear on the PCB.

## Phase 4: Visual Feedback Loop for Qwythos (NEW)

> [!IMPORTANT]
> The user requested letting the `qwythos-9b-96k` subagent "see" the generated `board.pdf` and `.kicad_pcb` files to iteratively adjust its output via Vision-Language capabilities.

To add this capability, we propose:
1. **PDF/SVG Rasterizer**: In the Studio CLI (`export_final_pcb.py`), add a script that automatically rasterizes the KiCad-CLI exported PDF/SVG into standard `.png` images.
2. **Qwythos Vision Tool**: Since the tiny_steward local agent uses `qwythos-9b-96k` with context length 98k (as seen in `config.yaml` changes), we will provide a `view_image` tool directly to the steward architecture (or the relevant studio task), allowing it to process the image and provide self-correcting `(x,y)` adjustments to the placement JSON.
3. **Live UI Sync**: Expose a visual preview in the UI where the user can watch Qwythos iterating on the board layout live.

---

## Verification Plan

### Automated Tests
```powershell
python -Xutf8 -c "from examples.export_final_pcb import export_json_to_pcb; export_json_to_pcb('knowledge/data/validation_complex/runs/20260716_004628_validate_20260716_004628_69e81d47/pulselab_zero.json')"
```

### Manual Verification
- Open the generated `.kicad_sch` in KiCad 10.0.3 — should open **without** the "older version" warning
- Verify components have visible pin graphics and readable values
- Verify the schematic has a logical spatial layout (not a single horizontal line)
