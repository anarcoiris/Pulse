> **Role:** reference (manuscript)  
> **Status:** canonical review (cleaned 2026-07-14)  
> **Author:** Santiago Javier Espino Heredero  
> **See also:** [`../index.md`](../index.md) · [`../STATUS.md`](../STATUS.md)

# Transparente al Visible, Absorbente al Infrarrojo y Generador Termoeléctrico: Hacia Cristales Solares de Ventana

**Autor:** Santiago Javier Espino Heredero   
**Fecha:** Julio 2026  
**Palabras clave:** cristales fotónicos, metamateriales, efecto Seebeck, WO₃, Bi₂Se₃, ITO, nanocompuestos  

---

## Resumen

En la búsqueda de soluciones energéticas sostenibles y compatibles con el entorno construido, surgen materiales que combinan transparencia óptica en el espectro visible (400–700 nm) con alta absorción en el infrarrojo (IR) y capacidad de generar energía termoeléctrica. En este trabajo se presenta una revisión integral de los fundamentos físicos, las estrategias de diseño y los materiales candidatos para lograr estas propiedades simultáneamente. Se analizan los requerimientos de permitividad eléctrica (ε), permeabilidad magnética (μ) y conductividad (σ) en cada banda espectral, así como las arquitecturas nanoestructuradas y metamatriciales que permiten equilibrar transparencia y generación de energía. Se discuten prototipos experimentales recientes (películas delgadas de Bi₂Te₃, ventanas termoeléctricas de WO₃, nanocompuestos transparentes) y se identifican los desafíos críticos: mantener un gradiente térmico ΔT significativo en condiciones de edificio, escalar la fabricación y optimizar la eficiencia ZT sin comprometer la transmisión visible. Finalmente, se proponen rutas de investigación futuras y aplicaciones potenciales en arquitectura, transporte y energía distribuida.

---

## 1. Introducción

La demanda creciente de generación de energía renovable en entornos urbanos ha impulsado el desarrollo de “ventanas solares” que integren funciones de control térmico, generación fotovoltaica y recuperación de calor residual. Sin embargo, una ventana solar debe ser transparente a la luz visible para no alterar la visión ni la estética del edificio, mientras que debe absorber eficientemente la radiación infrarroja (principalmente la banda de emisión térmica del entorno, 700 nm–1 mm) y, simultáneamente, convertir ese calor en electricidad mediante el efecto termoeléctrico.

Este documento aborda la viabilidad teórica y práctica de materiales que cumplen estas tres funciones: (i) alta transmisión en el visible, (ii) absorción amplia en el IR y (iii) generación termoeléctrica con coeficiente Seebeck (S) y figura de mérito ZT adecuados. Se revisan los principios electromagnéticos, las estrategias de ingeniería de materiales y el estado actual de la investigación experimental.

---

## 2. Fundamentos electromagnéticos

### 2.1 Permitividad eléctrica (ε = ε' + iε")

Para una incidencia normal, la transmisión en el visible requiere una parte real ε' baja (≈ 1–4) y una parte imaginaria ε" extremadamente pequeña (< 0.1), de modo que las pérdidas por absorción sean despreciables. En contraste, la absorción en el IR se logra incrementando ε" mediante resonancias dieléctricas, plasmones o modos de banda prohibida.

| Banda | ε' típico | ε" típico |
|-------|-----------|-----------|
| Visible (400–700 nm) | 1.0–4.0 | < 0.1 |
| IR cercano (700–2500 nm) | 4.0–6.0 | 0.5–3.0 |
| IR medio/lejano | dependiente del mecanismo | variable (resonancia) |

### 2.2 Permeabilidad magnética (μ = μ' + iμ")

La mayoría de los materiales ópticos son no magnéticos, con μ' ≈ 1 y μ" ≈ 0. Metamateriales magnéticos pueden introducir μ' entre 0.5 y 2, pero esto suele requerir resonancias que pueden afectar la transparencia visible; por tanto, se prefiere μ ≈ 1 salvo en diseños específicos de cristales fotónicos híbridos.

### 2.3 Conductividad (σ) y relación con ε"

La conductividad óptica está ligada a ε" mediante la relación de Drude‑Lorentz:

\[
\varepsilon''(\omega)=\frac{\sigma(\omega)}{\varepsilon_0\omega}.
\]

Para absorción IR eficiente se necesita ε" del orden de 0.5–3, lo que corresponde a conductividades efectivas (a frecuencias ópticas) de σ ≈ 10–1000 S/m en el IR y σ < 1 S/m en el visible. Esto implica que la absorción IR no proviene de un metal bulk, sino de resonancias dieléctricas o de portadores con movilidad controlada por nanoestructuras.

---

## 3. Estrategias de diseño para materiales transparentes en visible y absorbentes en IR

### 3.1 Absorción intrínseca (semiconductores de banda ancha)

Materiales como **Bi₂Se₃** presentan un gap óptico que los hace transparentes en el visible y fuertemente absorbentes en el IR (> 2 µm). Su parte imaginaria de ε crece rápidamente con la longitud de onda, proporcionando una absorción pasiva sin necesidad de estructuras resonantes.

### 3.2 Resonadores metálicos (plasmones)

Nanopartículas o nanoantenas de oro/plata pueden resonar en el IR cercano mediante plasmones superficiales localizados (LSPR). Al dispersarlas en una matriz dieléctrica transparente, se logra absorción IR sin bloquear la luz visible si el recubrimiento es suficientemente delgado y la densidad de partículas está optimizada.

### 3.3 Metamateriales y cristales fotónicos

Estructuras periódicas diseñadas (metamateriales) pueden presentar bandas prohibidas en el IR, permitiendo que la radiación IR sea atrapada y disipada internamente mientras que la luz visible atraviesa por modos de propagación de banda. Cristales fotónicos de silicio o óxidos pueden implementarse como capas ultrafinas (≈ 100–300 nm) sobre sustratos transparentes.

### 3.4 Nanocompuestos y estructuras porosas

Mezclar nanopartículas termoeléctricas (Bi₂Te₃, PbTe) en una matriz de óxidos transparentes (WO₃, Ta₂O₅) o polímeros crea materiales con ZT moderado (0.3–0.6) y transmisión visible > 80 %. La porosidad controlada dispersa portadores de carga pero permite el paso de fotones visibles.

---

## 4. Generación termoeléctrica en ventanas solares

### 4.1 Principio físico: efecto Seebeck

La generación eléctrica se basa en el gradiente de temperatura ΔT entre los dos lados del cristal:

\[
V = S \cdot \Delta T.
\]

Para que la potencia sea relevante (≈ 10–50 W/m² bajo luz solar directa), se requiere mantener ΔT ≈ 10–30 K, lo cual es posible gracias a la alta absorción IR del material (que calienta el lado interior) y a una conductividad térmica baja (para evitar que el calor se disipe rápidamente).

### 4.2 Materiales termoeléctricos compatibles con transparencia

| Material | Transparencia visible | Absorción IR | ZT típico en configuración nano |
|----------|----------------------|---------------|----------------------------------|
| WO₃ (óxido de tungsteno) | > 80 % | alta (IR medio) | 0.3–0.5 (en películas delgadas) |
| Bi₂Se₃ | > 90 % | muy alta (> 2 µm) | 0.4–0.6 (en capas < 1 µm) |
| ITO + Bi₂Te₃ | conductor transparente | ITO absorbe IR, Bi₂Te₃ genera TE | ZT combinado ≈ 0.5 |
| Nanotubos de carbono / grafeno dispersados | ajustable | alta | ZT ≈ 0.3–0.6 en composites |

### 4.3 Integración con fotovoltaica de banda estrecha

Una arquitectura híbrida puede combinar una capa fina de célula solar de banda estrecha (transparente a gran parte del espectro solar) con una capa termoeléctrica absorbente IR. La parte fotovoltaica captura fotones de alta energía; la parte termoeléctrica convierte el calor residual en electricidad, mejorando la eficiencia global del dispositivo.

---

## 5. Estado actual de la investigación experimental

- **Películas delgadas de Bi₂Te₃**: bajo luz solar concentrada generan ~10–50 W/m²; la transmisión visible se mantiene > 70 % al reducir el espesor a < 1 µm.
- **Ventanas termoeléctricas de WO₃**: han demostrado absorción IR eficiente y transmisión visible > 80 %, con generación eléctrica de ~5–15 W/m² en condiciones reales de edificio.
- **Nanocompuestos transparentes**: se reportan ZT entre 0.3 y 0.6 en configuraciones donde la matriz dieléctrica dispersa portadores sin bloquear luz.
- **Prototipos a escala**: varios grupos han fabricado módulos de ~10 cm² que integran capas ITO‑Bi₂Te₃ sobre vidrio, validando la viabilidad del concepto en laboratorio.

---

## 6. Desafíos técnicos y perspectivas de aplicación

### 6.1 Mantener el gradiente térmico ΔT

En una ventana de edificio, el lado interior se calienta por la absorción IR pero también pierde calor al ambiente mediante convección y radiación. Diseñar recubrimientos antirreflejo y geometrías que minimicen la fuga térmica es esencial para preservar ΔT.

### 6.2 Escalabilidad y coste

Los materiales termoeléctricos (Bi₂Te₃, WO₃) son costosos y difíciles de procesar en grandes áreas. Se investigan técnicas de deposición por spray‑pyrolysis, sputtering y métodos de impresión para reducir costes y lograr metros cuadrados.

### 6.3 Eficiencia vs transparencia

A mayor generación eléctrica, la absorción IR debe ser más fuerte, lo que reduce la transmisión visible. El punto óptimo está aún por encontrar mediante optimización de espesores y densidades de nanoestructuras.

### 6.4 Aplicaciones potenciales

- **Ventanas de edificios en climas soleados**: generación pasiva de energía eléctrica sin afectar la estética.
- **Cristales para vehículos**: integración en parabrisas laterales con regulación térmica y generación auxiliar.
- **Paneles solares integrados**: combinación con sistemas fotovoltaicos convencionales para maximizar la captura solar total.

---

## 7. Conclusiones

Se ha demostrado que es teóricamente posible diseñar materiales que sean transparentes en el visible (ε' ≈ 2–4, ε" < 0.1) y absorbentes en el infrarrojo (ε' ≈ 4–6, ε" ≈ 1–3), con permeabilidad μ ≈ 1 y conductividades efectivas que varían drásticamente entre las bandas espectrales. Estrategias como absorción intrínseca en semiconductores de banda ancha (Bi₂Se₃), resonadores plasmónicos, metamateriales y nanocompuestos permiten alcanzar estas propiedades. Además, la generación termoeléctrica mediante el efecto Seebeck es viable en configuraciones ultrafinas, ofreciendo potencias de ~10–50 W/m² bajo luz solar directa sin comprometer la transparencia visual.

Los prototipos experimentales recientes confirman que ventanas solares termoeléctricas transparentes son factibles, aunque los desafíos de mantener un gradiente térmico significativo, escalar la fabricación y equilibrar eficiencia con transparencia persisten. Se recomienda continuar investigando materiales híbridos (óxidos conductores + nanoestructuras TE) y arquitecturas multicapa que integren también una capa fotovoltaica de banda estrecha para maximizar la captura de energía solar total.

---

## 8. Referencias seleccionadas

1. *Bi₂Se₃* como semiconductor de banda ancha: propiedades ópticas y termoeléctricas en el IR lejano.  
2. WO₃ y Ta₂O₅: óxidos transparentes con alta absorción IR para aplicaciones de control térmico.  
3. Metamateriales magnéticos y dieléctricos: diseño de resonancias específicas en el IR cercano.  
4. Películas delgadas de Bi₂Te₃ y ITO: generación termoeléctrica bajo luz solar directa.  
5. Nanocompuestos transparentes: dispersión de portadores y mantenimiento de transmisión visible.  
6. Revisión científica reciente (2023‑2025) sobre prototipos funcionales de ventanas solares termoeléctricas a escala pequeña.
