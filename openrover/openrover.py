import sys
import warnings

import roverpro

warnings.warn('Please use the roverpro package instead of the openrover package.')

sys.modules['openrover'] = roverpro
