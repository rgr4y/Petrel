"""Encoder/button input from Klipper instead of host GPIO.

With PETREL_KLIPPER_INPUT=/tmp/dwin_input (the input_pty of a Klipper
[uart_bridge] section), the knob is wired to the printer board and Klipper
streams raw pin levels: one ASCII digit per change, bit0 = first pin.
Those levels drive gpiozero mock pins, so RotaryEncoder/Button decoding,
debounce and hold timing stay exactly as on GPIO.

Pin order in Klipper's input_pins must match (encoder A, encoder B, button).
"""
import os
import threading

ENV = 'PETREL_KLIPPER_INPUT'


def pin_factory(pins):
    """Return the gpiozero pin factory for this host. pins = (a, b, button)."""
    path = os.environ.get(ENV, '')
    if not path:
        from gpiozero.pins.lgpio import LGPIOFactory
        return LGPIOFactory()
    from gpiozero.pins.mock import MockFactory
    factory = MockFactory()
    feeder = threading.Thread(target=_feed, args=(factory, path, tuple(pins)),
                              name='klipper-input', daemon=True)
    feeder.start()
    return factory


def apply_state(factory, pins, state):
    for bit, number in enumerate(pins):
        pin = factory.pin(number)
        high = bool(state >> bit & 1)
        if pin.state != high:
            pin.drive_high() if high else pin.drive_low()


def _latest(data):
    digits = [c for c in data if 48 <= c <= 55]
    return digits[-1] - 48 if digits else None


def _feed(factory, path, pins):
    import time
    while True:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            time.sleep(1)  # Klipper not up yet / restarting
            continue
        try:
            # Discard backlog from while nobody was reading (stale clicks),
            # keep only the last level as the starting state.
            backlog = b''
            while True:
                try:
                    chunk = os.read(fd, 4096)
                except BlockingIOError:
                    break
                if not chunk:
                    break
                backlog += chunk
            state = _latest(backlog)
            if state is not None:
                apply_state(factory, pins, state)
            os.set_blocking(fd, True)
            while True:
                data = os.read(fd, 64)
                if not data:
                    break
                for c in data:
                    if 48 <= c <= 55:
                        apply_state(factory, pins, c - 48)
        except OSError:
            pass  # Klipper restarted: pty gone, reopen the new one
        finally:
            os.close(fd)
        time.sleep(1)
