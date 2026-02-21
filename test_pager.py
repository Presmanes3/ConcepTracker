import sys
import time
from rich.console import Console

console = Console()

def _getch_with_timeout(timeout: float = 0.2):
    if sys.platform == "win32":
        import msvcrt
        start = time.time()
        while time.time() - start < timeout:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):
                    return "arrow", msvcrt.getch()
                return "char", ch
            time.sleep(0.02)
        return None, None
    return None, None

last_size = console.size
count = 0
while True:
    kind, key = _getch_with_timeout(0.1)
    if kind is None:
        if console.size != last_size:
            print(f"Size changed from {last_size} to {console.size}")
            last_size = console.size
            break
        continue
    print(f"Key pressed: {kind}, {key}")
    break
