DEBUG_LEVEL = 0

def dprint(*args, level=1, **kwargs):
    if DEBUG_LEVEL >= level:
        print(*args, **kwargs)
