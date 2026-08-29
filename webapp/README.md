# PulseLab Web EDA Studio

Frontend web moderno para la plataforma **PulseLab Forge**, desarrollado con **React 19, TypeScript, Vite, Tailwind CSS y Three.js**.

---

## 🎨 Características Principales

- **Visor 2D Interactivo (`PCBViewer2D`)**: Canvas HTML5 acelerado con renderizado de pistas, serigrafía, componentes interactivos con drag-and-drop en tiempo real y cálculo de courtyards.
- **Visor 3D WebGL (`PCBViewer3D`)**: Renderizado tridimensional fotorrealista de la placa de circuito con texturas de máscara de soldadura, serigrafía y modelos de componentes.
- **Visor de Esquemáticos (`SchematicViewer`)**: Visualización interactiva de netlists y esquemas KiCad.
- **Tabla de Cadena de Suministro (`BOMSupplyChainTable`)**: Búsqueda en vivo y comparación de disponibilidad de componentes entre **JLCPCB (LCSC)** y **PCBWay**.
- **Co-Pilot IA Multisesión (`AIChatDrawer`)**: Asistente generativo para sintetizar topologías de circuitos, aplicar parches y consultar el motor RAG.
- **Reportes DRC en Tiempo Real (`DRCReportModal`)**: Visualización y auditoría de reglas de diseño geométrico y topológico.
- **Gestión de Modelos LLM (`LLMEnginePanel` & `LLMServiceModal`)**: Configuración de backends locales (Ollama / Qwythos / LLaMA) y proveedores cloud.

---

## 🚀 Puesta en Marcha

### Prerrequisitos

- **Node.js 18+** y `npm`
- Servidor backend de PulseLab ejecutándose en `http://localhost:8000` (vía `python -m uvicorn app.main:app --port 8000` o `./scripts/launch-pulselab.ps1`).

### Instalación y Ejecución

```bash
# 1. Instalar dependencias
npm install

# 2. Iniciar servidor de desarrollo
npm run dev
```

La aplicación estará disponible en `http://localhost:5173`.

### Compilación para Producción

```bash
npm run build
```

Los archivos estáticos optimizados se generarán en la carpeta `dist/` para ser servidos por FastAPI o Caddy en despliegues Docker.
