import pygame
import numpy as np
import math
import time
import random
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# ─────────────────────────────────────────────────────────
#  CONFIGURACIÓN Y CONSTANTES AVANZADAS
# ─────────────────────────────────────────────────────────
W, H = 1400, 900
FPS = 60
SIM_SCALE = 0.002  # Escala de tiempo para ver la física

# Colores Estilo "Terminal Industrial"
BG            = (5, 7, 10)
GRID          = (20, 25, 35)
ACCENT        = (0, 255, 180)   # Cyan neón
WARN          = (255, 180, 0)   # Ámbar
DANGER        = (255, 50, 50)   # Rojo sangre
SAFE          = (50, 255, 100)  # Verde esmeralda
DIM           = (100, 110, 130)
WHITE         = (240, 245, 255)
PANEL_BG      = (15, 18, 25)
PANEL_BORDER  = (45, 55, 75)

# ─────────────────────────────────────────────────────────
#  MODELO DE LA VÍCTIMA (CIRCUITO AISLADO)
# ─────────────────────────────────────────────────────────
class VictimCircuit:
    """Representa un microcontrolador vulnerable al EMP."""
    def __init__(self):
        self.is_dead = False
        self.glitch_intensity = 0.0
        self.memory_bits = [random.choice([0, 1]) for _ in range(16)]
        self.logic_error_count = 0
        self.uptime = 0.0
        self.health = 100.0 # 0 a 100

    def receive_pulse(self, pulse_energy: float, distance_factor: float):
        if self.is_dead: return

        # El daño depende de la energía y la "distancia" (simulada)
        impact = pulse_energy * distance_factor
        
        # 1. Efecto de Bit-Flip (Error lógico)
        if impact > 0.5:
            num_flips = int(impact * 5)
            for _ in range(num_flips):
                idx = random.randint(0, len(self.memory_bits)-1)
                self.memory_bits[idx] ^= 1 # Flip bit
                self.logic_error_count += 1
            self.glitch_intensity = min(1.0, impact * 0.5)
        
        # 2. Efecto de Daño Físico (Hard Failure)
        if impact > 5.0:
            damage = (impact - 5.0) * 10
            self.health -= damage
            if self.health <= 0:
                self.is_dead = True
                self.health = 0

    def update(self, dt):
        if not self.is_dead:
            self.uptime += dt
            self.glitch_intensity *= 0.9 # El glitch se disipa
        else:
            self.glitch_intensity = 1.0

# ─────────────────────────────────────────────────────────
#  MOTOR FÍSICO MEJORADO
# ─────────────────────────────────────────────────────────
@dataclass
class SystemConfig:
    v_source: float = 5000.0
    c_total: float = 0.6e-6
    r_pfn: float = 50.0
    r_charge: float = 10000.0
    efficiency: float = 0.95 # Acoplamiento antena

class PhysicsEngine:
    def __init__(self, config: SystemConfig):
        self.cfg = config
        self.reset()

    def reset(self):
        self.v_cap = 0.0
        self.charging = False
        self.armed = False
        self.purging = False
        self.pulse_active = False
        self.pulse_t = 0.0
        self.temp = 25.0 # Temperatura en °C
        self.wear = 0.0  # Degradación de componentes
        
        # Historial para gráficas
        self.history_v = deque(maxlen=200)
        self.history_p = deque(maxlen=200)
        self.pulse_count = 0

    def step(self, dt):
        # 1. Carga RC (con resistencia variable por temperatura)
        r_eff = self.cfg.r_charge * (1 + (self.temp - 25) * 0.01)
        tau_charge = r_eff * self.cfg.c_total
        
        if self.charging and not self.pulse_active:
            dv = (self.cfg.v_source - self.v_cap) * (1.0 - math.exp(-dt / tau_charge))
            self.v_cap += dv
            # El proceso de carga genera calor
            self.temp += 0.05 * dt

        # 2. Pulso PFN (Modelado más realista)
        pulse_v = 0.0
        if self.pulse_active:
            self.pulse_t += dt
            # Duración del pulso basada en L y C
            tau_pfn = 150e-9 # 150ns simplificado
            t_norm = self.pulse_t / tau_pfn
            
            if t_norm < 1.0:
                # Perfil de pulso con jitter y ruido
                env = math.sin(math.pi * t_norm) # Pulso suave semicircular
                pulse_v = (self.v_cap * self.cfg.efficiency) * env
                pulse_v += random.gauss(0, pulse_v * 0.05)
            else:
                self.pulse_active = False
                self.v_cap *= 0.1 # Descarga residual
                self.temp += 5.0  # El disparo genera un pico de calor
                self.pulse_count += 1
                self.wear += 0.01

        # 3. Enfriamiento pasivo
        self.temp += (25.0 - self.temp) * 0.1 * dt
        
        self.history_v.append(self.v_cap)
        self.history_p.append(pulse_v)

    def fire(self) -> float:
        if self.armed and self.v_cap > 500:
            self.pulse_active = True
            self.pulse_t = 0.0
            # Retorna la energía liberada (Joules)
            return 0.5 * self.cfg.c_total * (self.v_cap**2)
        return 0.0

# ─────────────────────────────────────────────────────────
#  SISTEMA DE PARTÍCULAS Y EFECTOS
# ─────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color, speed, life):
        self.x, self.y = x, y
        self.vx = random.uniform(-speed, speed)
        self.vy = random.uniform(-speed, speed)
        self.color = color
        self.life = life
        self.max_life = life

class EffectManager:
    def __init__(self):
        self.particles: List[Particle] = []
        self.screen_flash = 0.0

    def emit(self, x, y, color, n, speed):
        for _ in range(n):
            self.particles.append(Particle(x, y, color, speed, random.uniform(0.5, 1.0)))

    def update(self, dt):
        self.screen_flash = max(0, self.screen_flash - dt * 2)
        for p in self.particles[:]:
            p.x += p.vx
            p.y += p.vy
            p.life -= dt * 2
            if p.life <= 0:
                self.particles.remove(p)

    def draw(self, surf):
        for p in self.particles:
            alpha = int((p.life / p.max_life) * 255)
            s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*p.color, alpha), (2, 2), 2)
            surf.blit(s, (p.x, p.y))
        
        if self.screen_flash > 0:
            flash = pygame.Surface((W, H), pygame.SRCALPHA)
            flash.fill((255, 255, 255, int(self.screen_flash * 100)))
            surf.blit(flash, (0, 0))

# ─────────────────────────────────────────────────────────
#  CLASE PRINCIPAL DE INTERFAZ (UI)
# ─────────────────────────────────────────────────────────
class SimulatorApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("EMP LAB v2.0 - High Power Pulse Simulator")
        self.clock = pygame.time.Clock()
        self.font_main = pygame.font.SysFont("Consolas", 16)
        self.font_bold = pygame.font.SysFont("Consolas", 20, bold=True)
        self.font_ui = pygame.font.SysFont("Consolas", 14)

        self.config = SystemConfig()
        self.physics = PhysicsEngine(self.config)
        self.victim = VictimCircuit()
        self.effects = EffectManager()
        
        self.running = True
        self.log = deque(maxlen=10)

    def add_log(self, msg, color=WHITE):
        self.log.append((msg, color))

    def draw_crt_effect(self):
        """Efecto de lineas de escaneo CRT con transparencia real (SRCALPHA)."""
        crt_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 3):
            pygame.draw.line(crt_surf, (0, 0, 0, 50), (0, y), (W, y))
        self.screen.blit(crt_surf, (0, 0))

    def draw_ui(self):
        self.screen.fill(BG)
        # Dibujar Grid
        for x in range(0, W, 40): pygame.draw.line(self.screen, GRID, (x, 0), (x, H))
        for y in range(0, H, 40): pygame.draw.line(self.screen, GRID, (0, y), (W, y))

        # --- PANEL IZQUIERDO: CONFIGURACIÓN ---
        self.draw_panel(20, 20, 300, 400, "PARÁMETROS DE POTENCIA")
        y_off = 60
        params = [
            ("V. Fuente (kV)", f"{self.config.v_source/1000:.1f}", self.config.v_source/5000),
            ("Capacitancia (µF)", f"{self.config.c_total*1e6:.1f}", 0.5),
            ("Resist. PFN (Ω)", f"{self.config.r_pfn:.0f}", self.config.r_pfn/200),
            ("Eficiencia (%)", f"{self.config.efficiency*100:.0f}", self.config.efficiency),
        ]
        for label, val, scale in params:
            txt = self.font_ui.render(f"{label}: {val}", True, WHITE)
            self.screen.blit(txt, (40, y_off))
            pygame.draw.rect(self.screen, DIM, (40, y_off+20, 260, 5))
            pygame.draw.rect(self.screen, ACCENT, (40, y_off+20, 260 * scale, 5))
            y_off += 45

        # --- PANEL CENTRAL: ESQUEMA Y OSCILOSCOPIO ---
        self.draw_panel(340, 20, 720, 350, "MONITOR DE PULSO (REAL-TIME)")
        if len(self.physics.history_p) > 2:
            pts = []
            for i, v in enumerate(self.physics.history_p):
                x = 350 + (i / 200) * 700
                y = 350 - (v / (self.config.v_source * 0.6)) * 300
                pts.append((x, y))
            pygame.draw.lines(self.screen, DANGER, False, pts, 2)

        # --- PANEL DERECHO: VÍCTIMA (EL TARGET) ---
        self.draw_panel(1080, 20, 300, 400, "OBJETIVO (TARGET)")
        self.draw_victim_ui(1100, 60)

        # --- PANEL INFERIOR: LOG Y CONTROLES ---
        self.draw_panel(20, 440, 1360, 150, "SISTEMA DE CONTROL & LOG")
        self.draw_controls(40, 470)
        
        y_log = 470
        for msg, col in self.log:
            txt = self.font_ui.render(f"> {msg}", True, col)
            self.screen.blit(txt, (800, y_log))
            y_log += 18

        # --- ESTADO FÍSICO ---
        stats_y = 620
        stats = [
            (f"Temp: {self.physics.temp:.1f} °C", SAFE if self.physics.temp < 50 else DANGER),
            (f"Desgaste: {self.physics.wear*100:.1f}%", WARN if self.physics.wear > 0.1 else WHITE),
            (f"Disparos: {self.physics.pulse_count}", WHITE),
        ]
        for s_txt, s_col in stats:
            txt = self.font_bold.render(s_txt, True, s_col)
            self.screen.blit(txt, (20, stats_y))
            stats_y += 30

        self.draw_crt_effect()

    def draw_panel(self, x, y, w, h, title):
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, PANEL_BG, rect, border_radius=5)
        pygame.draw.rect(self.screen, PANEL_BORDER, rect, 2, border_radius=5)
        t_surf = self.font_bold.render(title, True, DIM)
        self.screen.blit(t_surf, (x + 10, y - 20))

    def draw_victim_ui(self, x, y):
        # Dibujar el chip
        rect = pygame.Rect(x, y, 260, 150)
        color = DANGER if self.victim.is_dead else (50, 50, 50)
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        pygame.draw.rect(self.screen, WHITE, rect, 2, border_radius=10)
        
        # Salud
        health_bar = pygame.Rect(x+10, y+10, 240, 10)
        pygame.draw.rect(self.screen, (20, 20, 20), health_bar)
        pygame.draw.rect(self.screen, SAFE, (x+10, y+10, 240 * (self.victim.health/100), 10))
        
        # Memoria (bits)
        for i in range(16):
            bx = x + 15 + (i % 8) * 30
            by = y + 40 + (i // 8) * 30
            bit_col = WHITE if self.victim.memory_bits[i] == 1 else (40, 40, 40)
            # Efecto glitch en bits
            if self.victim.glitch_intensity > 0.1:
                if random.random() < self.victim.glitch_intensity:
                    bit_col = DANGER
            
            pygame.draw.rect(self.screen, bit_col, (bx, by, 20, 20))
            pygame.draw.rect(self.screen, DIM, (bx, by, 20, 20), 1)

        if self.victim.is_dead:
            death_txt = self.font_bold.render("CRITICAL FAILURE", True, DANGER)
            self.screen.blit(death_txt, (x + 40, y + 120))

    def draw_controls(self, x, y):
        controls = [
            ("[S] Carga", "Activar/Desactivar"),
            ("[A] Armar", "Preparar sistema"),
            ("[SPACE] DISPARO", "Liberar Pulso EMP"),
            ("[P] Purga", "Descarga Segura"),
            ("[R] Reset", "Reiniciar todo"),
            ("[UP/DN] V-Source", "Ajustar Voltaje")
        ]
        for i, (k, d) in enumerate(controls):
            tx = x + (i * 220)
            k_surf = self.font_bold.render(k, True, ACCENT)
            d_surf = self.font_ui.render(d, True, DIM)
            self.screen.blit(k_surf, (tx, y))
            self.screen.blit(d_surf, (tx, y + 25))

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_s:
                        self.physics.charging = not self.physics.charging
                        self.add_log(f"Carga: {'ON' if self.physics.charging else 'OFF'}")
                    if event.key == pygame.K_a:
                        self.physics.armed = not self.physics.armed
                        self.add_log(f"Sistema {'ARMADO' if self.physics.armed else 'DESARMADO'}", 
                                    DANGER if self.physics.armed else SAFE)
                    if event.key == pygame.K_SPACE:
                        if self.physics.armed and self.physics.v_cap > 500:
                            energy = self.physics.fire()
                            self.effects.screen_flash = 1.0
                            self.effects.emit(700, 200, DANGER, 50, 15)
                            # Impactar la víctima
                            self.victim.receive_pulse(energy, 0.0001)
                            self.add_log("¡PULSO DISPARADO!", DANGER)
                        else:
                            self.add_log("FALLO DE DISPARO: Interlock activo", WARN)
                    if event.key == pygame.K_p:
                        self.physics.purging = True
                        self.physics.charging = False
                        self.add_log("Purga de seguridad activada", WARN)
                    if event.key == pygame.K_r:
                        self.physics = PhysicsEngine(self.config)
                        self.victim  = VictimCircuit()
                        self.add_log("Sistema reiniciado", ACCENT)
                    if event.key == pygame.K_UP:
                        self.config.v_source = min(10000, self.config.v_source + 500)
                    if event.key == pygame.K_DOWN:
                        self.config.v_source = max(1000, self.config.v_source - 500)

            # Update physics
            self.physics.step(SIM_SCALE)
            self.victim.update(dt)
            self.effects.update(dt)
            
            # Purga: descarga RC correcta con tau = R_PURGA * C_total
            # Ref: v(t) = v0 * exp(-t/tau)  =>  dv = v * (1 - exp(-dt/tau))
            if self.physics.purging:
                tau_purga = 50_000.0 * self.config.c_total   # R_PURGA * C
                dv = self.physics.v_cap * (1.0 - math.exp(-dt / tau_purga))
                self.physics.v_cap = max(0.0, self.physics.v_cap - dv)
                if self.physics.v_cap < 1.0:
                    self.physics.v_cap   = 0.0
                    self.physics.purging = False
                    self.add_log("Purga completada", SAFE)

            # Draw
            self.draw_ui()
            self.effects.draw(self.screen)
            
            pygame.display.flip()

        pygame.quit()

if __name__ == "__main__":
    app = SimulatorApp()
    app.run()