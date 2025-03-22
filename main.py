#!/usr/bin/env python3
"""
Main entry point for Ollama Flow application.
"""

import sys
import os
# Ensure the directory is in the Python path
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import OllamaFlow
from PySide6.QtWidgets import QApplication

def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)
    window = OllamaFlow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
