import builtins
from datetime import datetime

def print_banner():
    banner = "BANNER"
    print(banner)

print_banner()

_orig_print = builtins.print
def t_print(*args, **kwargs):
    _orig_print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", *args, **kwargs)
builtins.print = t_print

print("This is a test")
print(f"Another test")
