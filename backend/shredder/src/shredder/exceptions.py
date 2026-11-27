
class ShredderError(Exception):
    """General Shredder error."""
    pass

class ShredderConversionError(Exception):
    """Shredder error occurring within spawned PDF2HTMLEX process."""
    pass

__all__ = [
    "ShredderError",
]
