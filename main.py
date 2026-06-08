#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nothing_app.application import SomethingXApplication

if __name__ == "__main__":
    app = SomethingXApplication()
    sys.exit(app.run(sys.argv))
