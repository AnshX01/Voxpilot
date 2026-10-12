import sys
import threading
sys.path.insert(0, 'src')
from voxpilot.automation.uia_provider import UiaElementProvider

u = UiaElementProvider()
res = []

def run():
    elems = u.discover_elements()
    res.extend(elems)

t = threading.Thread(target=run)
t.start()
t.join()
print(f"Discovered elements count on worker thread: {len(res)}")
for e in res[:10]:
    print(f"  [{e.element_id}] {e.name} ({e.control_type}) -> {e.rect.to_tuple()}")
