import threading

def start_timer(minutes, callback):
    # Runs the callback after 'minutes' have passed
    t = threading.Timer(minutes * 60.0, callback)
    t.daemon = True
    t.start()
