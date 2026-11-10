from .client import AceClient
from .results import AceError, BinaryResult

Client = AceClient
__version__ = "0.2.0"
__all__ = ["AceClient", "Client", "AceError", "BinaryResult", "__version__"]
