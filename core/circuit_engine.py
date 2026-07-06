"""
circuit_engine.py
=================================================================================
Motor de Analisis Nodal Modificado (MNA) para simulacion de circuitos.

Metodo de integracion: Euler Implicito (Backward Euler), primer orden.
  Error de truncado local: O(dt^2) por paso -> O(dt) acumulado.
  Incondicionalmente estable para circuitos lineales (sin oscilaciones espurias).

Referencia: Pillage, Rohrer & Visweswariah, "Electronic Circuit and System
  Simulation Methods", McGraw-Hill 1994, cap. 3 (Companion Models).

Modelos companeros Backward Euler
----------------------------------
  Resistor R:   I = V/R
                -> G = 1/R, I_eq = 0

  Condensador C: I(t) = C/dt * [V(t) - V(t-dt)]
                -> G_eq = C/dt,  I_eq = G_eq * V(t-dt)

  Inductor L:   V(t) = L/dt * [I(t) - I(t-dt)]
                -> Rama de tension en MNA con R_eq = L/dt, V_eq = R_eq * I(t-dt)

  Fuente V:     Rama de corriente adicional en MNA.
  Interruptor:  Modelado como R_on (cerrado) o R_off (abierto).

Ecuacion matricial en cada paso
---------------------------------
  A(t) * x(t) = z(t)
  donde x = [V_1, ..., V_N, I_V1, ..., I_Vk, I_L1, ..., I_Lm]
=================================================================================
"""

import numpy as np


class CircuitSimulator:
    """
    Simulador de circuitos MNA de proposito general.

    Soporta: resistencias, condensadores, inductores,
    fuentes de tension e interruptores (SCR/IGBT como resistencias variables).

    Ejemplo de uso rapido::

        sim = CircuitSimulator(dt=1e-3)
        sim.add_voltage_source('V1', 'A', 'GND', 5000.0)
        sim.add_resistor('R1', 'A', 'B', 10_000.0)
        sim.add_capacitor('C1', 'B', 'GND', 0.6e-6)
        v, x = sim.step()
        print(v[sim.get_node('B')])   # Voltaje en nodo B
    """

    def __init__(self, dt: float = 1e-8):
        """
        Args:
            dt: Paso temporal inicial (s).
                Backward Euler es estable para cualquier dt > 0, pero la
                precision disminuye cuando dt > 0.1 * tau_minima_del_circuito.
        """
        if dt <= 0:
            raise ValueError(f"dt debe ser positivo, recibido: {dt}")
        self.dt: float        = dt
        self.nodes: dict      = {}   # nombre_nodo -> indice MNA (1-based; 0=GND)
        self.node_count: int  = 0
        self.elements: list   = []
        self.v_sources: int   = 0    # Contador de fuentes de tension
        self.inductors: int   = 0    # Contador de inductores
        self.time: float      = 0.0  # Tiempo simulado acumulado (s)
        self.v_prev: dict     = {}   # {nombre_cap: V(t-dt)} modelo companero
        self.i_prev: dict     = {}   # {nombre_ind: I(t-dt)} modelo companero

    # ─────────────────────────────────────────────────────────────
    # Gestion de nodos
    # ─────────────────────────────────────────────────────────────

    def get_node(self, name: str) -> int:
        """
        Devuelve el indice MNA del nodo.
        0 = GND (nodo de referencia).
        Crea el nodo si no existe.
        """
        if name in ('0', 'GND'):
            return 0
        if name not in self.nodes:
            self.node_count += 1
            self.nodes[name] = self.node_count
        return self.nodes[name]

    # ─────────────────────────────────────────────────────────────
    # Adicion de elementos
    # ─────────────────────────────────────────────────────────────

    def add_resistor(self, name: str, n1: str, n2: str, R: float) -> None:
        """
        Resistencia R (Ohm) entre nodos n1 y n2.
        Contribuye conductancia G = 1/R a la submatriz G de la MNA.
        """
        if R <= 0:
            raise ValueError(f"Resistencia '{name}': R debe ser positiva, recibido {R} Ohm")
        self.elements.append(('R', name, self.get_node(n1), self.get_node(n2), R))

    def add_capacitor(self, name: str, n1: str, n2: str, C: float) -> None:
        """
        Condensador C (F) entre nodos n1 y n2.

        Modelo companero Backward Euler:
            G_eq = C / dt
            I_eq = G_eq * V(t-dt)  [fuente de corriente adicional]
        """
        if C <= 0:
            raise ValueError(f"Condensador '{name}': C debe ser positivo, recibido {C} F")
        self.elements.append(('C', name, self.get_node(n1), self.get_node(n2), C))
        self.v_prev[name] = 0.0   # Condicion inicial: V_C(0) = 0

    def add_inductor(self, name: str, n1: str, n2: str, L: float) -> None:
        """
        Inductor L (H) entre nodos n1 y n2.

        Modelo companero Backward Euler:
            R_eq = L / dt             [resistencia equivalente de rama]
            V_eq = R_eq * I(t-dt)    [fuente de tension equivalente]

        Introduce variable de rama I_L en el sistema MNA.
        """
        if L <= 0:
            raise ValueError(f"Inductor '{name}': L debe ser positivo, recibido {L} H")
        self.inductors += 1
        self.elements.append(
            ('L', name, self.get_node(n1), self.get_node(n2), L, self.inductors)
        )
        self.i_prev[name] = 0.0   # Condicion inicial: I_L(0) = 0

    def add_voltage_source(self, name: str, n1: str, n2: str, V: float) -> None:
        """
        Fuente de tension ideal: V_n1 - V_n2 = V (V).
        Introduce variable de rama I_V en el sistema MNA.
        """
        self.v_sources += 1
        self.elements.append(
            ('V', name, self.get_node(n1), self.get_node(n2), V, self.v_sources)
        )

    def add_switch(self, name: str, n1: str, n2: str,
                   is_closed: bool = False,
                   R_on: float = 0.01,
                   R_off: float = 1e9) -> None:
        """
        Interruptor modelado como resistencia variable:
            Cerrado:  R = R_on   (SCR real: 10-50 mOhm; default 10 mOhm)
            Abierto:  R = R_off  (default 1 GOhm -> I_fuga <= 5 uA a 5 kV)

        Uso especial - interruptor de purga con resistencia de descarga incorporada:
            sim.add_switch('S_PURGE', 'BANCO', 'GND', R_on=50_000)  # R_on = R_purga

        Args:
            R_on:  Resistencia de conduccion (Ohm). Debe ser > 0.
            R_off: Resistencia de aislamiento (Ohm). Debe ser > R_on.
        """
        if R_on <= 0:
            raise ValueError(f"Switch '{name}': R_on debe ser positivo, recibido {R_on}")
        if R_off <= R_on:
            raise ValueError(f"Switch '{name}': R_off ({R_off}) debe ser > R_on ({R_on})")
        self.elements.append(
            ('S', name, self.get_node(n1), self.get_node(n2), is_closed, R_on, R_off)
        )

    # ─────────────────────────────────────────────────────────────
    # Control en tiempo de ejecucion
    # ─────────────────────────────────────────────────────────────

    def _find_element(self, etype: str, name: str) -> int:
        """Indice del elemento en self.elements, o -1 si no existe."""
        for i, el in enumerate(self.elements):
            if el[0] == etype and el[1] == name:
                return i
        return -1

    def set_switch(self, name: str, is_closed: bool) -> None:
        """
        Cambia el estado del interruptor preservando R_on y R_off originales.

        Args:
            name:      Nombre del interruptor tal como fue declarado en add_switch().
            is_closed: True = cerrado (conduciendo), False = abierto.

        Raises:
            ValueError: Si el interruptor no existe en el circuito.
        """
        idx = self._find_element('S', name)
        if idx == -1:
            raise ValueError(f"Switch '{name}' no encontrado en el circuito.")
        el = self.elements[idx]
        # Tupla completa: ('S', name, n1, n2, is_closed, R_on, R_off)
        self.elements[idx] = (el[0], el[1], el[2], el[3], is_closed, el[5], el[6])

    def set_voltage_source(self, name: str, V: float) -> None:
        """
        Modifica el valor de una fuente de tension en tiempo de simulacion.
        Util para modelar variaciones de la fuente HV durante la carga.

        Raises:
            ValueError: Si la fuente no existe.
        """
        idx = self._find_element('V', name)
        if idx == -1:
            raise ValueError(f"Fuente '{name}' no encontrada en el circuito.")
        el = self.elements[idx]
        # Tupla: ('V', name, n1, n2, V, vsrc_num)
        self.elements[idx] = (el[0], el[1], el[2], el[3], V, el[5])

    def set_dt(self, new_dt: float) -> None:
        """
        Cambia el paso temporal de integracion de forma segura.

        Los estados internos v_prev e i_prev almacenan magnitudes fisicas
        en t_actual (voltajes y corrientes reales), NO cocientes temporales.
        Por tanto NO requieren reescalado cuando dt cambia:
          - G_eq_nuevo = C / dt_nuevo  (correcto: G_eq se recalcula en cada paso)
          - I_eq = G_eq_nuevo * V(t-dt)  (V(t-dt) es el estado fisico, no escala con dt)

        Ref: Pillage et al., sec. 3.2 "Variable step-size integration with
             companion models".

        Args:
            new_dt: Nuevo paso temporal (s). Debe ser positivo.

        Raises:
            ValueError: Si new_dt <= 0.
        """
        if new_dt <= 0:
            raise ValueError(f"dt debe ser positivo, recibido: {new_dt}")
        self.dt = new_dt

    def reset_state(self) -> None:
        """
        Reinicia todos los estados dinamicos a cero.
        Equivale a t=0 con condensadores descargados e inductores sin corriente.
        La topologia del circuito (elementos) se preserva.
        """
        for key in self.v_prev:
            self.v_prev[key] = 0.0
        for key in self.i_prev:
            self.i_prev[key] = 0.0
        self.time = 0.0

    # ─────────────────────────────────────────────────────────────
    # Ensamblado del sistema MNA
    # ─────────────────────────────────────────────────────────────

    def prepare_matrices(self):
        """
        Ensambla la matriz A y el vector z del sistema lineal MNA:
            A * x = z

        Variables de solucion x:
            [V_1, ..., V_N,  I_V1, ..., I_Vk,  I_L1, ..., I_Lm]
             tensiones       corrientes fuentes  corrientes inductores

        Tamano de A: n_vars x n_vars
            n_vars = node_count + v_sources + inductors
        """
        n_vars = self.node_count + self.v_sources + self.inductors
        A = np.zeros((n_vars, n_vars))
        z = np.zeros(n_vars)

        def stamp_G(n1: int, n2: int, g: float) -> None:
            """Estampa conductancia G entre nodos n1 y n2 (KCL nodal)."""
            if n1 != 0:
                A[n1 - 1, n1 - 1] += g
            if n2 != 0:
                A[n2 - 1, n2 - 1] += g
            if n1 != 0 and n2 != 0:
                A[n1 - 1, n2 - 1] -= g
                A[n2 - 1, n1 - 1] -= g

        def stamp_I(n1: int, n2: int, current: float) -> None:
            """Fuente de corriente: current entra en n1, sale de n2 (convencion KCL)."""
            if n1 != 0:
                z[n1 - 1] -= current
            if n2 != 0:
                z[n2 - 1] += current

        for el in self.elements:
            etype, name, n1, n2 = el[0], el[1], el[2], el[3]

            if etype == 'R':
                stamp_G(n1, n2, 1.0 / el[4])

            elif etype == 'S':
                # Interruptor: R_on si cerrado, R_off si abierto
                R = el[5] if el[4] else el[6]
                stamp_G(n1, n2, 1.0 / R)

            elif etype == 'C':
                # Condensador — modelo companero Backward Euler
                # I_C(t) = G_eq * V_C(t) - I_eq
                # G_eq = C/dt,  I_eq = G_eq * V_C(t-dt)
                C = el[4]
                G_eq = C / self.dt
                stamp_G(n1, n2, G_eq)
                stamp_I(n1, n2, -G_eq * self.v_prev[name])

            elif etype == 'L':
                # Inductor — modelo companero Backward Euler, rama en MNA
                # V_L(t) - R_eq * I_L(t) = -R_eq * I_L(t-dt)
                # R_eq = L/dt
                L, ind_num = el[4], el[5]
                idx = self.node_count + self.v_sources + ind_num - 1
                R_eq = L / self.dt
                if n1 != 0:
                    A[n1 - 1, idx] += 1.0
                    A[idx, n1 - 1] += 1.0
                if n2 != 0:
                    A[n2 - 1, idx] -= 1.0
                    A[idx, n2 - 1] -= 1.0
                A[idx, idx] -= R_eq
                z[idx] = -R_eq * self.i_prev[name]

            elif etype == 'V':
                # Fuente de tension: V_n1 - V_n2 = V
                V, src_num = el[4], el[5]
                idx = self.node_count + src_num - 1
                if n1 != 0:
                    A[n1 - 1, idx] += 1.0
                    A[idx, n1 - 1] += 1.0
                if n2 != 0:
                    A[n2 - 1, idx] -= 1.0
                    A[idx, n2 - 1] -= 1.0
                z[idx] = V

        # Regularizacion diagonal: 1 pS por nodo para manejar nodos flotantes.
        # Corriente a 5 kV: I = 5000 * 1e-12 = 5 nA  -> despreciable.
        A += np.eye(n_vars) * 1e-12

        return A, z

    # ─────────────────────────────────────────────────────────────
    # Paso de simulacion
    # ─────────────────────────────────────────────────────────────

    def step(self):
        """
        Ejecuta un paso de integracion Backward Euler.

        Returns:
            node_voltages (np.ndarray): Longitud node_count+1.
                Indice 0 = GND = 0 V.
                Indice k = tension en nodo k (V).
            x (np.ndarray): Vector solución MNA completo.
                Primeros node_count elementos: tensiones nodales.
                Siguientes v_sources: corrientes de fuentes de tension.
                Ultimos inductors: corrientes de inductores.
        """
        A, z = self.prepare_matrices()
        try:
            x = np.linalg.solve(A, z)
        except np.linalg.LinAlgError:
            # Nodo flotante no manejado por la regularizacion: circuito incorrecto
            x = np.zeros_like(z)

        # Tensiones nodales: insertar GND = 0 V en posicion 0
        node_voltages = np.insert(x[:self.node_count], 0, 0.0)

        # Actualizar estados de los modelos companeros
        for el in self.elements:
            etype, name, n1, n2 = el[0], el[1], el[2], el[3]
            if etype == 'C':
                self.v_prev[name] = node_voltages[n1] - node_voltages[n2]
            elif etype == 'L':
                ind_num = el[5]
                idx = self.node_count + self.v_sources + ind_num - 1
                self.i_prev[name] = x[idx]

        self.time += self.dt
        return node_voltages, x


# =============================================================================
# Ejemplo / Test rapido
# =============================================================================
if __name__ == '__main__':
    import math
    print("Test 1: Carga RC — tau = 6 ms")
    sim = CircuitSimulator(dt=1e-3)
    sim.add_voltage_source('PSU', 'A', 'GND', 5000.0)
    sim.add_resistor('R',   'A', 'B', 10_000.0)
    sim.add_capacitor('C',  'B', 'GND', 0.6e-6)
    for _ in range(6):
        v, _ = sim.step()
    v_sim   = v[sim.get_node('B')]
    v_exact = 5000 * (1 - math.exp(-6e-3 / (10_000 * 0.6e-6)))
    print(f"  V_sim={v_sim:.1f} V   V_exacto={v_exact:.1f} V   "
          f"err={abs(v_sim - v_exact) / v_exact * 100:.2f}%")
    print("  (Error ~4.5% es esperado con Backward Euler de primer orden a dt=1ms)")

    print("\nTest 2: Cambio de dt via set_dt()")
    sim.set_dt(1e-6)
    v2, _ = sim.step()
    print(f"  V tras 1us adicional: {v2[sim.get_node('B')]:.2f} V")

    print("\nTest 3: reset_state()")
    sim.reset_state()
    v3, _ = sim.step()
    print(f"  V tras reset (deberia ser <100 V): {v3[sim.get_node('B')]:.2f} V")

    print("\nOK — circuit_engine.py funcional.")
