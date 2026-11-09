"""Encoder/button input from Klipper instead of host GPIO.

With PETREL_KLIPPER_INPUT=/tmp/dwin_input (the input_pty of a Klipper
[uart_bridge] section), the knob is wired to the printer board and Klipper
streams raw pin levels: one ASCII digit per change, bit0 = first pin.
Those levels drive gpiozero mock pins, so RotaryEncoder/Button decoding,
debounce and hold timing stay exactly as on GPIO.

Pin order in Klipper's input_pins must match (encoder A, encoder B, button).

KlipperBeeper writes "B<freq> <duty>\n" back on the same pty; Klipper's
[uart_bridge] beeper option plays it on the board's beeper pin.
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


class KlipperBeeper:
    """Buzzer driver (HardwarePWM interface) for the printer board's beeper."""
    def __init__(self, path):
        self.path = path
        self.fd = None

    def _send(self, frequency, duty):
        line = b'B%d %.4f\n' % (round(frequency), duty)
        for _ in range(2):  # reopen once: Klipper restarts make a new pty
            try:
                if self.fd is None:
                    self.fd = os.open(self.path, os.O_WRONLY | os.O_NONBLOCK)
                os.write(self.fd, line)
                return
            except OSError:
                self.close_fd()
        raise OSError('Klipper beeper channel unavailable: ' + self.path)

    def close_fd(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def tone(self, frequency, volume):
        if not 0 <= volume <= 100:
            raise ValueError('Invalid volume')
        self.set_pwm(frequency, volume / 200.)

    def set_pwm(self, frequency, duty):
        if not 1 <= frequency <= 20000 or not 0 <= duty <= 1:
            raise ValueError('Invalid frequency/duty')
        self._send(frequency if duty else 0, duty)

    def off(self):
        self._send(0, 0.)

    def close(self):
        try:
            self.off()
        except OSError:
            pass
        self.close_fd()
