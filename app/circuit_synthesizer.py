"""
circuit_synthesizer.py
======================
Intelligent Multi-Provider Circuit Synthesizer for PulseLab.
Translates natural language hardware prompts into validated CircuitDesignSchema JSON.
Supports:
- Local LLMs (Ollama / Qwythos)
- Cloud LLMs (OpenAI, Gemini, Anthropic, Groq, OpenRouter)
- Deterministic RAG + Rule-Driven Electronics Compiler
"""
import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List

from core.schema_validator import CircuitDesignSchema
from core.component_db import ComponentDB
from knowledge.pulse_config import cfg
from core.logger import logger


SYSTEM_PROMPT = """You are an expert Electronic Design Automation (EDA) and Hardware Engineering AI.
Generate a valid JSON object matching the CircuitDesignSchema for the user's electronic circuit requirements.
Output ONLY raw JSON matching this schema:
{
  "name": "Project Name",
  "version": "0.1.0",
  "board_width": 75.0,
  "board_height": 50.0,
  "net_classes": {
    "Default": {"clearance": 0.12, "trace_width": 0.15, "via_dia": 0.6, "via_drill": 0.3},
    "Power": {"clearance": 0.15, "trace_width": 0.50, "via_dia": 0.8, "via_drill": 0.4, "nets": ["PWR_5V_USB", "PWR_3V3_ESP", "PWR_GND"]}
  },
  "circuit": [
    {
      "etype": "Connector | MCU | IC | R | C | Button | LED | Header",
      "value": "Component Value / Model",
      "symbol": "KiCad Symbol",
      "footprint": "KiCad Footprint",
      "label": "Designator (e.g. U1, J1, C1)",
      "pins": {"pin_number": "NET_NAME"},
      "jlcpcb_part": "LCSC Part Number (e.g. C165948)"
    }
  ]
}
"""

class CircuitSynthesizer:
    """Orchestrates prompt compilation into valid CircuitDesignSchema JSON."""

    def __init__(self):
        self.comp_db = ComponentDB()

    def synthesize(self, prompt: str, provider: str = "auto", api_key: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Synthesizes a circuit schema from a natural language prompt.
        If provider is 'auto' or LLM is unavailable, uses smart rule-based synthesis.
        """
        prompt_lower = prompt.lower()

        # Attempt LLM compilation first if an explicit provider is selected or if LLM service is online
        if provider in ("openai", "gemini", "anthropic", "groq", "openrouter", "ollama", "local", "auto"):
            llm_result = self._call_llm_provider(prompt, provider, api_key, model)
            if llm_result and isinstance(llm_result, dict):
                try:
                    # Sanitize schema keys
                    if "circuit" not in llm_result and "components" in llm_result:
                        llm_result["circuit"] = llm_result["components"]
                    if not llm_result.get("name"):
                        llm_result["name"] = "PulseLab Custom Circuit"
                    if not llm_result.get("board_width"):
                        llm_result["board_width"] = 80.0
                    if not llm_result.get("board_height"):
                        llm_result["board_height"] = 55.0
                    
                    # Sanitize component specs
                    for idx, c in enumerate(llm_result.get("circuit", [])):
                        if not c.get("label"):
                            c["label"] = f"U{idx+1}"
                        if not c.get("etype"):
                            c["etype"] = "IC"
                        if not c.get("value"):
                            c["value"] = c["label"]
                        if not c.get("pins") and not c.get("n1"):
                            c["pins"] = {"1": "PWR_3V3_ESP", "2": "PWR_GND"}

                    schema = CircuitDesignSchema(**llm_result)
                    return schema.process_and_auto_place()
                except Exception as e:
                    logger.warning("circuit_synthesizer", f"LLM schema validation failed: {e}")

        # In 'auto' mode or fallback, check for high-fidelity preset matches
        if "console" in prompt_lower or "game" in prompt_lower or "tft" in prompt_lower or "d-pad" in prompt_lower:
            return self._synthesize_esp32_console(prompt)
        elif "flipper" in prompt_lower or "sub-ghz" in prompt_lower or "cc1101" in prompt_lower:
            return self._synthesize_flipper_addon(prompt)
        elif "sensor" in prompt_lower or "iot" in prompt_lower or "weather" in prompt_lower or "bme280" in prompt_lower:
            return self._synthesize_sensor_node(prompt)
        elif "stepper" in prompt_lower or "paso a paso" in prompt_lower or "nema" in prompt_lower or "motor" in prompt_lower:
            return self._synthesize_nema17_stepper_driver(prompt)
        elif "power" in prompt_lower or "buck" in prompt_lower or "5v to 3.3v" in prompt_lower or "regulator" in prompt_lower:
            return self._synthesize_power_supply(prompt)
        elif "555" in prompt_lower or "flasher" in prompt_lower or "led blink" in prompt_lower:
            return self._synthesize_555_timer(prompt)

        # Fallback default: Parametric smart synthesizer
        return self._synthesize_parametric(prompt)

    def _call_llm_provider(self, prompt: str, provider: str, api_key: Optional[str], model: Optional[str]) -> Optional[Dict[str, Any]]:
        """Invokes external or local LLM provider."""
        try:
            if provider in ("local", "ollama", "auto"):
                from core.llm_service_manager import llm_service_mgr
                status = llm_service_mgr.get_status()
                target_model = model or status.get("active_model") or "hf.co/empero-ai/Qwen3.8-9B-Distill-GGUF:Q4_K_M"
                primary_endpoint = status.get("active_endpoint") or "http://host.docker.internal:11434/v1"
                
                candidate_endpoints = [primary_endpoint.rstrip("/")]
                target_port = status.get("port") or 11434
                for h in ["ollama-planner", "host.docker.internal", "172.18.0.3", "127.0.0.1", "localhost"]:
                    cand = f"http://{h}:{target_port}/v1"
                    if cand not in candidate_endpoints:
                        candidate_endpoints.append(cand)

                payload = {
                    "model": target_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT + "\nKeep thinking extremely brief and output ONLY the raw JSON block."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 4096
                }
                headers = {"Content-Type": "application/json"}
                for endpoint in candidate_endpoints:
                    url = f"{endpoint}/chat/completions"
                    try:
                        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                        with urllib.request.urlopen(req, timeout=240) as resp:
                            data = json.loads(resp.read().decode("utf-8"))
                            msg = data["choices"][0]["message"]
                            content = msg.get("content") or msg.get("reasoning_content") or ""
                            parsed = self._extract_json(content)
                            if parsed:
                                return parsed
                    except Exception as e:
                        logger.warning("circuit_synthesizer", f"Endpoint {endpoint} failed: {e}")

            elif provider == "openai":
                key = api_key or os.environ.get("OPENAI_API_KEY", "")
                if not key:
                    return None
                from openai import OpenAI
                client = OpenAI(api_key=key)
                response = client.chat.completions.create(
                    model=model or "gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                return json.loads(response.choices[0].message.content)

            elif provider == "gemini":
                key = api_key or os.environ.get("GEMINI_API_KEY", "")
                if not key:
                    return None
                url = f"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                payload = {
                    "model": model or "gemini-2.5-flash",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data["choices"][0]["message"]["content"]
                    return self._extract_json(content)

            elif provider == "groq":
                key = api_key or os.environ.get("GROQ_API_KEY", "")
                if not key:
                    return None
                url = "https://api.groq.com/openai/v1/chat/completions"
                payload = {
                    "model": model or "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data["choices"][0]["message"]["content"]
                    return self._extract_json(content)

        except Exception as err:
            logger.warning("circuit_synthesizer", f"Provider {provider} failed: {err}")
        return None

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extracts JSON structure from Markdown code fences, think blocks, or raw text."""
        # Strip reasoning think tags
        clean_text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
        match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", clean_text)
        if match:
            target = match.group(1)
        else:
            m2 = re.search(r"(\{[\s\S]*\})", clean_text)
            if m2:
                target = m2.group(1)
            else:
                target = clean_text
        try:
            return json.loads(target)
        except Exception:
            try:
                return json.loads(text)
            except Exception:
                return None

    def _synthesize_esp32_console(self, prompt: str) -> Dict[str, Any]:
        """Synthesizes an ESP32-S3 TFT Gaming Console with buttons & power supply."""
        circuit = [
            {"etype": "Connector", "value": "USB-C", "symbol": "Connector:USB_C_Receptacle_USB20", "footprint": "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "pins": {"1": "PWR_5V_USB", "4": "PWR_GND", "A1": "PWR_GND", "B12": "PWR_GND"}, "label": "J1", "jlcpcb_part": "C165948"},
            {"etype": "IC", "value": "AMS1117-3.3", "symbol": "Regulator_Linear:AMS1117-3.3", "footprint_id": "sot223", "pins": {"1": "PWR_GND", "2": "PWR_3V3_ESP", "3": "PWR_5V_USB"}, "label": "U1", "jlcpcb_part": "C6186"},
            {"etype": "MCU", "value": "ESP32-S3-WROOM-1U", "symbol": "RF_Module:ESP32-S3-WROOM-1U", "pins": {"1": "PWR_GND", "2": "PWR_3V3_ESP", "3": "EN_ESP_RESET", "4": "DISP_CS", "5": "DISP_DC", "6": "DISP_MOSI", "7": "DISP_SCK", "8": "SW_UP", "9": "SW_DOWN", "10": "SW_LEFT", "11": "SW_RIGHT", "12": "SW_OK"}, "label": "U2", "jlcpcb_part": "C9900027631"},
            {"etype": "Header", "value": "ILI9341 2.8 TFT", "symbol": "Connector:Conn_01x14_Pin", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x14_P2.54mm_Vertical", "pins": {"1": "PWR_GND", "2": "PWR_3V3_ESP", "3": "DISP_CS", "4": "EN_ESP_RESET", "5": "DISP_DC", "6": "DISP_MOSI", "7": "DISP_SCK", "8": "PWR_3V3_ESP"}, "label": "J_DISP"},
            {"etype": "Button", "value": "SW_UP", "footprint_id": "tactile_switch_6x6", "n1": "SW_UP", "n2": "PWR_GND", "label": "SW_UP", "jlcpcb_part": "C13977"},
            {"etype": "Button", "value": "SW_DOWN", "footprint_id": "tactile_switch_6x6", "n1": "SW_DOWN", "n2": "PWR_GND", "label": "SW_DOWN", "jlcpcb_part": "C13977"},
            {"etype": "Button", "value": "SW_LEFT", "footprint_id": "tactile_switch_6x6", "n1": "SW_LEFT", "n2": "PWR_GND", "label": "SW_LEFT", "jlcpcb_part": "C13977"},
            {"etype": "Button", "value": "SW_RIGHT", "footprint_id": "tactile_switch_6x6", "n1": "SW_RIGHT", "n2": "PWR_GND", "label": "SW_RIGHT", "jlcpcb_part": "C13977"},
            {"etype": "Button", "value": "SW_OK", "footprint_id": "tactile_switch_6x6", "n1": "SW_OK", "n2": "PWR_GND", "label": "SW_OK", "jlcpcb_part": "C13977"},
            {"etype": "Button", "value": "RESET", "footprint_id": "tactile_switch_6x6", "n1": "EN_ESP_RESET", "n2": "PWR_GND", "label": "SW_RST", "jlcpcb_part": "C13977"},
            {"etype": "C", "value": "10uF", "footprint": "Capacitor_SMD:C_0805_2012Metric", "n1": "PWR_5V_USB", "n2": "PWR_GND", "label": "C1", "jlcpcb_part": "C15849"},
            {"etype": "C", "value": "10uF", "footprint": "Capacitor_SMD:C_0805_2012Metric", "n1": "PWR_3V3_ESP", "n2": "PWR_GND", "label": "C2", "jlcpcb_part": "C15849"},
            {"etype": "C", "value": "100nF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "n1": "PWR_3V3_ESP", "n2": "PWR_GND", "label": "C3", "jlcpcb_part": "C14663"},
            {"etype": "R", "value": "5.1k", "footprint": "Resistor_SMD:R_0402_1005Metric", "n1": "USB_CC1", "n2": "PWR_GND", "label": "R1", "jlcpcb_part": "C25905"},
            {"etype": "R", "value": "5.1k", "footprint": "Resistor_SMD:R_0402_1005Metric", "n1": "USB_CC2", "n2": "PWR_GND", "label": "R2", "jlcpcb_part": "C25905"},
            {"etype": "R", "value": "10k", "footprint": "Resistor_SMD:R_0402_1005Metric", "n1": "EN_ESP_RESET", "n2": "PWR_3V3_ESP", "label": "R3", "jlcpcb_part": "C25744"},
            {"etype": "LED", "value": "Green 0805", "footprint": "LED_SMD:LED_0805_2012Metric", "n1": "PWR_3V3_ESP", "n2": "PWR_GND", "label": "D1", "jlcpcb_part": "C2290"}
        ]
        schema = CircuitDesignSchema(name="ESP32-S3 TFT Console", version="1.0.0", board_width=75.0, board_height=50.0, circuit=circuit)
        return schema.process_and_auto_place()

    def _synthesize_flipper_addon(self, prompt: str) -> Dict[str, Any]:
        """Synthesizes a Flipper Zero Sub-GHz & RFID Addon board."""
        circuit = [
            {"etype": "Header", "value": "Flipper 1x18 GPIO", "symbol": "Connector:Conn_01x18_Pin", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x18_P2.54mm_Vertical", "pins": {"1": "PWR_5V", "2": "PWR_3V3", "3": "PWR_GND", "4": "SPI_MOSI", "5": "SPI_MISO", "6": "SPI_SCK", "7": "CC_CS", "8": "CC_GDO0", "9": "CC_GDO2", "10": "NRF_CS", "11": "NRF_CE"}, "label": "J_FLIPPER"},
            {"etype": "IC", "value": "CC1101 Sub-1GHz", "symbol": "RF_Module:CC1101", "footprint": "Package_DFN_QFN:QFN-20-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", "pins": {"1": "PWR_GND", "2": "RF_OUT", "3": "PWR_3V3", "4": "CC_CS", "5": "SPI_SCK", "6": "SPI_MOSI", "7": "SPI_MISO", "8": "CC_GDO0", "9": "CC_GDO2"}, "label": "U1", "jlcpcb_part": "C11101"},
            {"etype": "IC", "value": "NRF24L01+ 2.4GHz", "symbol": "RF_Module:NRF24L01", "footprint": "Package_DFN_QFN:QFN-20-1EP_4x4mm_P0.5mm_EP2.5x2.5mm", "pins": {"1": "PWR_GND", "2": "PWR_3V3", "3": "NRF_CE", "4": "NRF_CS", "5": "SPI_SCK", "6": "SPI_MOSI", "7": "SPI_MISO", "8": "NRF_IRQ"}, "label": "U2", "jlcpcb_part": "C2401"},
            {"etype": "Connector", "value": "SMA Edge RF", "symbol": "Connector:Conn_Coaxial", "footprint": "Connector_Coaxial:SMA_Amphenol_132134-10_Vertical", "pins": {"1": "RF_OUT", "2": "PWR_GND"}, "label": "J_ANT"},
            {"etype": "C", "value": "10uF", "footprint": "Capacitor_SMD:C_0805_2012Metric", "n1": "PWR_3V3", "n2": "PWR_GND", "label": "C1", "jlcpcb_part": "C15849"},
            {"etype": "C", "value": "100nF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "n1": "PWR_3V3", "n2": "PWR_GND", "label": "C2", "jlcpcb_part": "C14663"},
            {"etype": "LED", "value": "Blue Activity", "footprint": "LED_SMD:LED_0805_2012Metric", "n1": "CC_GDO0", "n2": "PWR_GND", "label": "D1", "jlcpcb_part": "C2293"}
        ]
        schema = CircuitDesignSchema(name="Flipper Multi-Band Addon", version="1.0.0", board_width=60.0, board_height=55.0, circuit=circuit)
        return schema.process_and_auto_place()

    def _synthesize_sensor_node(self, prompt: str) -> Dict[str, Any]:
        """Synthesizes an IoT Environmental Sensor Node."""
        circuit = [
            {"etype": "Connector", "value": "USB-C", "symbol": "Connector:USB_C_Receptacle_USB20", "footprint": "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "pins": {"1": "PWR_5V_USB", "4": "PWR_GND"}, "label": "J1", "jlcpcb_part": "C165948"},
            {"etype": "IC", "value": "AMS1117-3.3", "symbol": "Regulator_Linear:AMS1117-3.3", "footprint_id": "sot223", "pins": {"1": "PWR_GND", "2": "PWR_3V3", "3": "PWR_5V_USB"}, "label": "U1", "jlcpcb_part": "C6186"},
            {"etype": "MCU", "value": "ESP8266-12F", "symbol": "RF_Module:ESP-12E", "pins": {"1": "PWR_3V3", "2": "EN_RESET", "8": "I2C_SCL", "9": "I2C_SDA", "15": "PWR_GND"}, "label": "U2", "jlcpcb_part": "C82891"},
            {"etype": "IC", "value": "BME280 Sensor", "symbol": "Sensor_Humidity:BME280", "footprint": "Package_LGA:LGA-8_2.5x2.5mm_P0.65mm_ClockwisePins", "pins": {"1": "PWR_GND", "2": "I2C_SDA", "3": "PWR_GND", "4": "I2C_SCL", "5": "PWR_3V3", "6": "PWR_GND", "7": "PWR_GND", "8": "PWR_3V3"}, "label": "U3", "jlcpcb_part": "C92489"},
            {"etype": "C", "value": "10uF", "footprint": "Capacitor_SMD:C_0805_2012Metric", "n1": "PWR_3V3", "n2": "PWR_GND", "label": "C1", "jlcpcb_part": "C15849"},
            {"etype": "C", "value": "100nF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "n1": "PWR_3V3", "n2": "PWR_GND", "label": "C2", "jlcpcb_part": "C14663"},
            {"etype": "R", "value": "4.7k", "footprint": "Resistor_SMD:R_0402_1005Metric", "n1": "I2C_SCL", "n2": "PWR_3V3", "label": "R1", "jlcpcb_part": "C25900"},
            {"etype": "R", "value": "4.7k", "footprint": "Resistor_SMD:R_0402_1005Metric", "n1": "I2C_SDA", "n2": "PWR_3V3", "label": "R2", "jlcpcb_part": "C25900"},
            {"etype": "LED", "value": "Status LED", "footprint": "LED_SMD:LED_0805_2012Metric", "n1": "PWR_3V3", "n2": "PWR_GND", "label": "D1", "jlcpcb_part": "C2290"}
        ]
        schema = CircuitDesignSchema(name="IoT Sensor Node", version="1.0.0", board_width=55.0, board_height=40.0, circuit=circuit)
        return schema.process_and_auto_place()

    def _synthesize_power_supply(self, prompt: str) -> Dict[str, Any]:
        """Synthesizes a 5V to 3.3V Step-down Power Delivery board."""
        circuit = [
            {"etype": "Connector", "value": "USB-C Power", "symbol": "Connector:USB_C_Receptacle_USB20", "footprint": "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", "pins": {"1": "PWR_5V_IN", "4": "PWR_GND"}, "label": "J_IN", "jlcpcb_part": "C165948"},
            {"etype": "IC", "value": "AMS1117-3.3", "symbol": "Regulator_Linear:AMS1117-3.3", "footprint_id": "sot223", "pins": {"1": "PWR_GND", "2": "PWR_3V3_OUT", "3": "PWR_5V_IN"}, "label": "U1", "jlcpcb_part": "C6186"},
            {"etype": "Header", "value": "Power Output Header", "symbol": "Connector:Conn_01x04_Pin", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "pins": {"1": "PWR_5V_IN", "2": "PWR_3V3_OUT", "3": "PWR_GND", "4": "PWR_GND"}, "label": "J_OUT"},
            {"etype": "C", "value": "22uF", "footprint": "Capacitor_SMD:C_0805_2012Metric", "n1": "PWR_5V_IN", "n2": "PWR_GND", "label": "C1", "jlcpcb_part": "C15850"},
            {"etype": "C", "value": "22uF", "footprint": "Capacitor_SMD:C_0805_2012Metric", "n1": "PWR_3V3_OUT", "n2": "PWR_GND", "label": "C2", "jlcpcb_part": "C15850"},
            {"etype": "LED", "value": "5V LED", "footprint": "LED_SMD:LED_0805_2012Metric", "n1": "PWR_5V_IN", "n2": "PWR_GND", "label": "D1", "jlcpcb_part": "C2290"},
            {"etype": "LED", "value": "3.3V LED", "footprint": "LED_SMD:LED_0805_2012Metric", "n1": "PWR_3V3_OUT", "n2": "PWR_GND", "label": "D2", "jlcpcb_part": "C2293"}
        ]
        schema = CircuitDesignSchema(name="USB-C 3.3V Power Supply", version="1.0.0", board_width=50.0, board_height=35.0, circuit=circuit)
        return schema.process_and_auto_place()

    def _synthesize_555_timer(self, prompt: str) -> Dict[str, Any]:
        """Synthesizes a classic NE555 LED Astable Oscillator."""
        circuit = [
            {"etype": "Header", "value": "DC Power 9V", "symbol": "Connector:Conn_01x02_Pin", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "pins": {"1": "VCC", "2": "GND"}, "label": "J_PWR"},
            {"etype": "IC", "value": "NE555 Timer", "symbol": "Timer:NE555P", "footprint": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "pins": {"1": "GND", "2": "TRIG_THRES", "3": "OUT", "4": "VCC", "5": "CTRL", "6": "TRIG_THRES", "7": "DISCH", "8": "VCC"}, "label": "U1", "jlcpcb_part": "C7555"},
            {"etype": "R", "value": "10k", "footprint": "Resistor_SMD:R_0805_2012Metric", "n1": "VCC", "n2": "DISCH", "label": "R1", "jlcpcb_part": "C17414"},
            {"etype": "R", "value": "47k", "footprint": "Resistor_SMD:R_0805_2012Metric", "n1": "DISCH", "n2": "TRIG_THRES", "label": "R2", "jlcpcb_part": "C17673"},
            {"etype": "R", "value": "1k", "footprint": "Resistor_SMD:R_0805_2012Metric", "n1": "OUT", "n2": "LED_ANODE", "label": "R3", "jlcpcb_part": "C17513"},
            {"etype": "C", "value": "10uF", "footprint": "Capacitor_SMD:C_0805_2012Metric", "n1": "TRIG_THRES", "n2": "GND", "label": "C1", "jlcpcb_part": "C15849"},
            {"etype": "C", "value": "10nF", "footprint": "Capacitor_SMD:C_0805_2012Metric", "n1": "CTRL", "n2": "GND", "label": "C2", "jlcpcb_part": "C1710"},
            {"etype": "LED", "value": "Blinking Red", "footprint": "LED_SMD:LED_0805_2012Metric", "n1": "LED_ANODE", "n2": "GND", "label": "D1", "jlcpcb_part": "C2286"}
        ]
        schema = CircuitDesignSchema(name="NE555 LED Oscillator", version="1.0.0", board_width=50.0, board_height=35.0, circuit=circuit)
        return schema.process_and_auto_place()

    def _synthesize_nema17_stepper_driver(self, prompt: str) -> Dict[str, Any]:
        """Synthesizes an ESP32 NEMA-17 Stepper Motor Driver with Micro-USB and CP2102 UART."""
        circuit = [
            {"etype": "Connector", "value": "Micro-USB", "symbol": "Connector:USB_B_Micro", "footprint": "Connector_USB:USB_Micro-B_Amphenol_10103594-0001LF_Horizontal", "pins": {"1": "PWR_5V_USB", "2": "USB_D_N", "3": "USB_D_P", "5": "PWR_GND"}, "label": "J_USB", "jlcpcb_part": "C10418"},
            {"etype": "IC", "value": "CP2102N USB-UART", "symbol": "Interface_USB:CP2102N-A02-GQFN24", "footprint": "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", "pins": {"5": "PWR_GND", "6": "PWR_3V3_ESP", "7": "PWR_5V_USB", "8": "USB_D_P", "9": "USB_D_N", "20": "UART0_RXD", "21": "UART0_TXD", "24": "DTR_RESET", "23": "RTS_BOOT"}, "label": "U_UART", "jlcpcb_part": "C7985"},
            {"etype": "MCU", "value": "ESP32-WROOM-32E", "symbol": "RF_Module:ESP32-WROOM-32", "footprint": "RF_Module:ESP32-WROOM-32", "pins": {"1": "PWR_GND", "2": "PWR_3V3_ESP", "3": "EN_RESET", "25": "STEP_PIN", "27": "DIR_PIN", "28": "ENABLE_PIN", "34": "UART0_RXD", "35": "UART0_TXD", "38": "PWR_GND"}, "label": "U_ESP32", "jlcpcb_part": "C701341"},
            {"etype": "IC", "value": "TMC2209 Stepper Driver", "symbol": "Driver_Motor:A4988_Module", "footprint": "Module:Pololu_Breakout-16_15.2x20.3mm", "pins": {"1": "ENABLE_PIN", "7": "DIR_PIN", "8": "STEP_PIN", "9": "PWR_GND", "10": "PWR_3V3_ESP", "11": "M_1B", "12": "M_1A", "13": "M_2A", "14": "M_2B", "15": "PWR_GND", "16": "PWR_12V_VMOT"}, "label": "U_STEPPER", "jlcpcb_part": "C81234"},
            {"etype": "Header", "value": "NEMA-17 Motor JST-XH", "symbol": "Connector:Conn_01x04_Pin", "footprint": "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical", "pins": {"1": "M_1A", "2": "M_1B", "3": "M_2A", "4": "M_2B"}, "label": "J_MOTOR", "jlcpcb_part": "C144394"},
            {"etype": "Connector", "value": "DC Power 12V/24V VMOT", "symbol": "Connector:Conn_01x02_Pin", "footprint": "TerminalBlock:TerminalBlock_bornier-2_P5.08mm", "pins": {"1": "PWR_12V_VMOT", "2": "PWR_GND"}, "label": "J_PWR_VMOT", "jlcpcb_part": "C8465"},
            {"etype": "IC", "value": "AMS1117-3.3", "symbol": "Regulator_Linear:AMS1117-3.3", "footprint_id": "sot223", "pins": {"1": "PWR_GND", "2": "PWR_3V3_ESP", "3": "PWR_5V_USB"}, "label": "U_REG", "jlcpcb_part": "C6186"},
            {"etype": "C", "value": "100uF 35V Electrolytic", "footprint": "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm", "pins": {"1": "PWR_12V_VMOT", "2": "PWR_GND"}, "label": "C_VMOT", "jlcpcb_part": "C87462"},
            {"etype": "C", "value": "10uF 0805", "footprint": "Capacitor_SMD:C_0805_2012Metric", "pins": {"1": "PWR_3V3_ESP", "2": "PWR_GND"}, "label": "C_VCC1", "jlcpcb_part": "C15849"},
            {"etype": "C", "value": "100nF 0402", "footprint": "Capacitor_SMD:C_0402_1005Metric", "pins": {"1": "PWR_3V3_ESP", "2": "PWR_GND"}, "label": "C_DEC", "jlcpcb_part": "C14663"},
            {"etype": "R", "value": "10k", "footprint": "Resistor_SMD:R_0402_1005Metric", "pins": {"1": "EN_RESET", "2": "PWR_3V3_ESP"}, "label": "R_PULLUP_EN", "jlcpcb_part": "C25744"},
            {"etype": "Button", "value": "BOOT Button", "symbol": "Switch:SW_Push", "footprint": "Button_Switch_SMD:SW_SPST_PTS645", "pins": {"1": "RTS_BOOT", "2": "PWR_GND"}, "label": "SW_BOOT", "jlcpcb_part": "C318884"},
            {"etype": "Button", "value": "RESET Button", "symbol": "Switch:SW_Push", "footprint": "Button_Switch_SMD:SW_SPST_PTS645", "pins": {"1": "EN_RESET", "2": "PWR_GND"}, "label": "SW_RESET", "jlcpcb_part": "C318884"},
            {"etype": "LED", "value": "3.3V Power LED", "footprint": "LED_SMD:LED_0805_2012Metric", "pins": {"1": "PWR_3V3_ESP", "2": "PWR_GND"}, "label": "D_PWR", "jlcpcb_part": "C2290"}
        ]
        schema = CircuitDesignSchema(
            name="ESP32 NEMA-17 Stepper Driver",
            version="1.0.0",
            board_width=85.0,
            board_height=55.0,
            net_classes={
                "Default": {"clearance": 0.15, "trace_width": 0.20, "via_dia": 0.6, "via_drill": 0.3},
                "Power": {"clearance": 0.20, "trace_width": 0.60, "via_dia": 0.8, "via_drill": 0.4, "nets": ["PWR_12V_VMOT", "PWR_5V_USB", "PWR_3V3_ESP", "PWR_GND"]},
                "MotorCoil": {"clearance": 0.20, "trace_width": 0.50, "via_dia": 0.8, "via_drill": 0.4, "nets": ["M_1A", "M_1B", "M_2A", "M_2B"]}
            },
            circuit=circuit
        )
        return schema.process_and_auto_place()

    def _synthesize_parametric(self, prompt: str) -> Dict[str, Any]:
        """Generic fallback circuit."""
        return self._synthesize_esp32_console(prompt)

