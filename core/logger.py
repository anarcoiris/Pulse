import logging
import os
from collections import deque
from datetime import datetime

# Custom log level for AI reviews
AI_REVIEW_LEVEL = 25
logging.addLevelName(AI_REVIEW_LEVEL, "AI_REVIEW")

def ai_review(self, message, *args, **kws):
    if self.isEnabledFor(AI_REVIEW_LEVEL):
        self._log(AI_REVIEW_LEVEL, message, args, **kws)

logging.Logger.ai_review = ai_review

class PulseLogger:
    """
    Logger centralizado para PulseLab Forge con buffer circular para contexto de IA.
    Implementa el patrón Singleton.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PulseLogger, cls).__new__(cls)
            cls._instance._setup()
        return cls._instance

    def _setup(self):
        self.logger = logging.getLogger("PulseLab")
        self.logger.setLevel(logging.DEBUG)
        
        # Prevenir duplicación de handlers si se reinicializa
        if not self.logger.handlers:
            # Directorio de logs
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            # File Handler
            fh = logging.FileHandler(os.path.join(log_dir, "pulse_forge.log"), encoding='utf-8')
            fh.setLevel(logging.DEBUG)
            
            # Console Handler
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            
            # Formatter
            formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)
            
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)
        
        # AI Context Buffer (Memoria Circular)
        self.context_buffer = deque(maxlen=200)

    def _log_with_buffer(self, level_name: str, module: str, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{module}] [{level_name}] {message}"
        self.context_buffer.append(log_entry)
        
        level_num = getattr(logging, level_name, logging.INFO)
        if level_name == "AI_REVIEW":
            level_num = AI_REVIEW_LEVEL
            
        self.logger.log(level_num, f"[{module}] {message}")

    def debug(self, module: str, message: str): self._log_with_buffer("DEBUG", module, message)
    def info(self, module: str, message: str): self._log_with_buffer("INFO", module, message)
    def warning(self, module: str, message: str): self._log_with_buffer("WARNING", module, message)
    def error(self, module: str, message: str): self._log_with_buffer("ERROR", module, message)
    def ai_review(self, module: str, message: str): self._log_with_buffer("AI_REVIEW", module, message)

    def get_context(self) -> str:
        """Devuelve los últimos 200 logs como un string unificado."""
        return "\n".join(self.context_buffer)

# Instancia global (Singleton)
logger = PulseLogger()
