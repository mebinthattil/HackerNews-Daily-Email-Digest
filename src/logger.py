"""Centralized logging configuration with colors and progress helpers."""
import logging
import sys

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Levels
    DEBUG = "\033[36m"      # Cyan
    INFO = "\033[32m"       # Green
    WARNING = "\033[33m"    # Yellow
    ERROR = "\033[31m"      # Red
    CRITICAL = "\033[35m"   # Magenta
    
    # Special
    HEADER = "\033[1;34m"   # Bold Blue
    PROGRESS = "\033[36m"   # Cyan


class ColorFormatter(logging.Formatter):
    """Custom formatter with colors for terminal output."""
    
    COLORS = {
        logging.DEBUG: Colors.DEBUG,
        logging.INFO: Colors.INFO,
        logging.WARNING: Colors.WARNING,
        logging.ERROR: Colors.ERROR,
        logging.CRITICAL: Colors.CRITICAL,
    }
    
    def __init__(self, use_colors=True):
        super().__init__()
        self.use_colors = use_colors
    
    def format(self, record):
        if self.use_colors:
            color = self.COLORS.get(record.levelno, Colors.RESET)
            levelname = f"{color}[{record.levelname}]{Colors.RESET}"
        else:
            levelname = f"[{record.levelname}]"
        
        return f"{levelname} {record.getMessage()}"


def setup_logger(name: str = None) -> logging.Logger:
    """Get or create a logger with colored output.
    
    Args:
        name: Logger name (usually __name__). If None, returns root logger.
    
    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    
    # Only configure if no handlers exist on root logger
    root = logging.getLogger()
    if not root.handlers:
        # Check if output supports colors (TTY check)
        use_colors = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColorFormatter(use_colors=use_colors))
        
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    
    return logger


def log_section(title: str, logger: logging.Logger = None):
    """Log a section header for visual separation.
    
    Args:
        title: Section title.
        logger: Logger to use. If None, uses root logger.
    """
    if logger is None:
        logger = logging.getLogger()
    
    use_colors = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    
    if use_colors:
        header = f"\n{Colors.HEADER}{'═' * 3} {title.upper()} {'═' * 3}{Colors.RESET}"
    else:
        header = f"\n{'═' * 3} {title.upper()} {'═' * 3}"
    
    logger.info(header)


def log_progress(current: int, total: int, message: str, logger: logging.Logger = None):
    """Log a progress message with [current/total] prefix.
    
    Args:
        current: Current item number (1-indexed).
        total: Total number of items.
        message: Progress message.
        logger: Logger to use. If None, uses root logger.
    """
    if logger is None:
        logger = logging.getLogger()
    
    use_colors = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    
    if use_colors:
        prefix = f"{Colors.PROGRESS}[{current}/{total}]{Colors.RESET}"
    else:
        prefix = f"[{current}/{total}]"
    
    logger.info(f"{prefix} {message}")
