import ctypes
import threading

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
DESKTOP_ALL = 0x1FF

def worker():
    h_def = user32.OpenDesktopW("default", 0, False, DESKTOP_ALL)
    print(f"[Worker] OpenDesktopW: {h_def}")
    if not h_def:
        print("[Worker] Failed OpenDesktopW, err:", kernel32.GetLastError())
        return
    ret = user32.SetThreadDesktop(h_def)
    err = kernel32.GetLastError()
    print(f"[Worker] SetThreadDesktop: {ret}, err: {err}")
    if ret:
        hwnds = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def cb(hwnd, lparam):
            title_buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title_buf, 256)
            if title_buf.value:
                hwnds.append((hwnd, title_buf.value))
            return True
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        print(f"[Worker] Default desktop windows: {len(hwnds)}")
        for h, t in hwnds[:20]:
            print(f"   [{h}] {t}")

t = threading.Thread(target=worker)
t.start()
t.join()
