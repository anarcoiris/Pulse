import pygame
from pathlib import Path
from typing import Optional, Dict, List
from ui.theme import W, H, WHITE, DIM, ACCENT, ACCENT2, SAFE, WARN, DANGER, PANEL_BG, draw_panel, draw_text
from ui.properties import TextInput

class BaseModal:
    """Base class for all modal popups."""
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.visible = False
        self.close_rect = pygame.Rect(0, 0, 1, 1)

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def draw_background(self, surf: pygame.Surface) -> tuple[int, int, pygame.Rect]:
        # Dim background
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        surf.blit(dim, (0, 0))

        px, py = (W - self.width) // 2, (H - self.height) // 2
        p_rect = pygame.Rect(px, py, self.width, self.height)
        return px, py, p_rect

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if event was consumed."""
        if not self.visible:
            return False
            
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect.collidepoint(event.pos):
                self.hide()
                return True
        return True # Default consume all input when modal is visible


class ForgeResultModal(BaseModal):
    def __init__(self):
        super().__init__(700, 480)
        self.info = {}
        self.dir_rect = pygame.Rect(0, 0, 1, 1)
        self.on_open_dir = None

    def show_result(self, output_dir: str, pcb: str, sch: str, fw: Optional[str], stats: dict):
        self.info = {
            "output_dir": output_dir,
            "pcb": pcb,
            "sch": sch,
            "fw": fw,
            "stats": stats
        }
        self.show()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect.collidepoint(event.pos):
                self.hide()
                return True
            elif self.dir_rect.collidepoint(event.pos):
                if self.on_open_dir:
                    self.on_open_dir(self.info.get("output_dir", ""))
                return True
        return True

    def draw(self, surf: pygame.Surface, fonts: dict):
        if not self.visible: return
        px, py, p_rect = self.draw_background(surf)
        draw_panel(surf, p_rect, border_col=ACCENT)
        
        draw_text(surf, "🚀 PulseLab Forge: Proyecto Finalizado", px + 30, py + 20, fonts['bold'], ACCENT)
        
        y = py + 80
        stats = self.info.get("stats", {})
        
        items = [
            ("PROYECTO", Path(self.info.get("pcb", "")).name.replace(".kicad_pcb", ".kicad_pro"), SAFE),
            ("ESQUEMA",  Path(self.info.get("sch", "")).name, SAFE),
            ("PLACA",    Path(self.info.get("pcb", "")).name, SAFE),
            ("RENDER 3D", self.info.get("render_status", ""), ACCENT2),
        ]
        if self.info.get("fw"):
            items.append(("FIRMWARE", Path(self.info["fw"]).name, WARN))
        
        for icon, text, col in items:
            draw_text(surf, icon, px + 40, y, fonts['bold'], DIM)
            draw_text(surf, text, px + 220, y, fonts['md'], col)
            y += 35
            
        y += 20
        draw_text(surf, "Métricas del Layout:", px + 40, y, fonts['bold'], WHITE)
        y += 25
        stats_txt = f"Tamaño: {stats.get('board_mm', '?')}  |  Componentes: {stats.get('footprints', 0)}  |  Nets: {stats.get('nets', 0)}"
        draw_text(surf, stats_txt, px + 50, y, fonts['xs'], DIM)
        
        btn_y = py + self.height - 65
        bw, bh = 220, 40
        self.dir_rect = pygame.Rect(px + 40, btn_y, bw, bh)
        pygame.draw.rect(surf, (20, 30, 50), self.dir_rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT2, self.dir_rect, 1, border_radius=5)
        draw_text(surf, "ABRIR CARPETA PROYECTO", px + 40 + bw//2, btn_y + bh//2, fonts['sm'], ACCENT2, 'center')
        
        self.close_rect = pygame.Rect(px + self.width - 140, btn_y, 100, bh)
        pygame.draw.rect(surf, PANEL_BG, self.close_rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT, self.close_rect, 1, border_radius=5)
        draw_text(surf, "Cerrar", px + self.width - 140 + 50, btn_y + bh//2, fonts['sm'], WHITE, 'center')


class AIGeneratorModal(BaseModal):
    def __init__(self):
        super().__init__(700, 260)
        # TextInput(rect, initial, max_len)
        self.input_field = TextInput(pygame.Rect(0, 0, 620, 36), "", max_len=1000)
        self.submit_rect = pygame.Rect(0,0,1,1)
        self.loading = False
        self.error = ""
        self.on_submit = None

    def show_prompt(self, on_submit):
        self.on_submit = on_submit
        self.error = ""
        self.loading = False
        self.input_field.active = True
        self.show()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible: return False
        if self.loading: return True
        
        self.input_field.handle_event(event)
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect.collidepoint(event.pos):
                self.hide()
            elif self.submit_rect.collidepoint(event.pos):
                self._submit()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            if self.input_field.active:
                self._submit()
        return True

    def _submit(self):
        text = self.input_field.text.strip()
        if not text:
            self.error = "Escribe una descripción."
            return
        if self.on_submit:
            self.on_submit(text)

    def draw(self, surf: pygame.Surface, fonts: dict):
        if not self.visible: return
        px, py, p_rect = self.draw_background(surf)
        draw_panel(surf, p_rect, border_col=(0, 200, 180))
        
        draw_text(surf, "🧠 Generador de Circuitos IA (Qwen 2.5)", px + 20, py + 15, fonts['bold'], (0, 200, 180))
        draw_text(surf, "Describe el circuito y la IA creará la topología.", px + 20, py + 45, fonts['xs'], DIM)
        
        self.input_field.rect.x = px + 20
        self.input_field.rect.y = py + 75
        self.input_field.rect.w = self.width - 40
        self.input_field.draw(surf, fonts['md'])
        
        y_status = py + 120
        if self.loading:
            draw_text(surf, "⏳ Generando topología... (Puede tardar uns seg.)", px + 20, y_status, fonts['sm'], ACCENT)
        elif self.error:
            draw_text(surf, f"Error: {self.error}", px + 20, y_status, fonts['xs'], DANGER)
            
        btn_w, btn_h = 120, 35
        self.submit_rect = pygame.Rect(px + self.width - btn_w*2 - 30, py + self.height - btn_h - 20, btn_w, btn_h)
        if not self.loading:
            pygame.draw.rect(surf, (0, 80, 50), self.submit_rect, border_radius=5)
            pygame.draw.rect(surf, SAFE, self.submit_rect, 1, border_radius=5)
            draw_text(surf, "Generar", self.submit_rect.centerx, self.submit_rect.centery, fonts['sm'], SAFE, 'center')
        
        self.close_rect = pygame.Rect(px + self.width - btn_w - 20, py + self.height - btn_h - 20, btn_w, btn_h)
        pygame.draw.rect(surf, PANEL_BG, self.close_rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT, self.close_rect, 1, border_radius=5)
        draw_text(surf, "Cerrar", self.close_rect.centerx, self.close_rect.centery, fonts['sm'], WHITE, 'center')


class AIReviewModal(BaseModal):
    def __init__(self):
        super().__init__(600, 400)
        self.loading = False
        self.issues = []
        self.fix_rect = None
        self.on_fix = None

    def show_review(self, on_fix):
        self.loading = True
        self.issues = []
        self.fix_rect = None
        self.on_fix = on_fix
        self.show()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible: return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_rect.collidepoint(event.pos):
                self.hide()
            elif self.fix_rect and self.fix_rect.collidepoint(event.pos):
                if self.on_fix:
                    self.on_fix()
                self.hide()
        return True

    def draw(self, surf: pygame.Surface, fonts: dict):
        if not self.visible: return
        px, py, p_rect = self.draw_background(surf)
        # Fix the background for review modal to use 150 alpha
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        surf.blit(dim, (0, 0))
        draw_panel(surf, p_rect, border_col=(60, 200, 255))
        
        draw_text(surf, "✦ Asistente AI (Revisión Semántica y DRC)", px + 20, py + 15, fonts['bold'], WHITE)
        
        y = py + 60
        if self.loading:
            draw_text(surf, "Evaluando netlist local y reglas KiCad... (Espere)", px + self.width//2, py + self.height//2, fonts['sm'], ACCENT, 'center')
        else:
            if not self.issues:
                draw_text(surf, "¡Circuito 100% impecable! No se detectaron problemas.", px + 20, y, fonts['sm'], SAFE)
            else:
                draw_text(surf, f"Se detectaron {len(self.issues)} problemas semánticos/físicos:", px + 20, y, fonts['sm'], WARN)
                y += 30
                can_auto_fix = False
                for idx, iss in enumerate(self.issues[:4]): 
                    sev_col = DANGER if iss.get("severity") == "critical" else (220,160,40)
                    texto = f"[{idx+1}] {iss.get('msg', '')}"
                    if "'0'" in texto and "'GND'" in texto:
                        can_auto_fix = True
                    draw_text(surf, texto, px + 30, y, fonts['xs'], sev_col)
                    y += 20
                    prop = iss.get("proposal", "")
                    if prop:
                        draw_text(surf, f"➜ {prop}", px + 50, y, fonts['xs'], DIM)
                        y += 25
                    else:
                        y += 10
                
                y = py + self.height - 60
                if can_auto_fix:
                    btn_fw, btn_fh = 220, 35
                    self.fix_rect = pygame.Rect(px + 20, y, btn_fw, btn_fh)
                    pygame.draw.rect(surf, (0, 80, 50), self.fix_rect, border_radius=5)
                    pygame.draw.rect(surf, SAFE, self.fix_rect, 1, border_radius=5)
                    draw_text(surf, "🛠 Merge '0' → 'GND'", px + 20 + btn_fw//2, y + btn_fh//2, fonts['sm'], SAFE, 'center')
                else:
                    self.fix_rect = None

        btn_w, btn_h = 100, 35
        self.close_rect = pygame.Rect(px + self.width - btn_w - 20, py + self.height - btn_h - 20, btn_w, btn_h)
        pygame.draw.rect(surf, PANEL_BG, self.close_rect, border_radius=5)
        pygame.draw.rect(surf, ACCENT, self.close_rect, 1, border_radius=5)
        draw_text(surf, "Cerrar", px + self.width - 20 - btn_w//2, py + self.height - 20 - btn_h//2, fonts['sm'], WHITE, 'center')
