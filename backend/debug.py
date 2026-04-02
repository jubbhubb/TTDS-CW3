DEBUG_LEVEL = 4

def dprint(*args, level=1, **kwargs):
    if DEBUG_LEVEL >= level:
        print(*args, **kwargs)
