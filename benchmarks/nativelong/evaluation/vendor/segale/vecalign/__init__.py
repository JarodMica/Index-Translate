import sys
import os

# Add the 'vecalign' directory itself to the Python path.
# This allows modules within this package to import each other directly by name.
package_dir = os.path.abspath(os.path.dirname(__file__))
if package_dir not in sys.path:
        sys.path.insert(0, package_dir)

