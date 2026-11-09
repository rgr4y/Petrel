"""klipper_input: Klipper pin-level stream drives Petrel's encoder and button.

Run: PYTHONPATH=. python3 tests/test_klipper_input.py
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

A, B, BTN = 26, 19, 13   # arbitrary GPIO numbers, as configured in Petrel


def wait_for(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def main():
    master, slave = os.openpty()
    import tty
    tty.setraw(slave)
    link = os.path.join(tempfile.mkdtemp(), 'dwin_input')
    os.symlink(os.ttyname(slave), link)

    # Backlog written before Petrel starts: a stale click, ending idle.
    # Must not produce a press.
    os.write(master, b'7' b'3' b'7')   # bits: A=1 B=2 BTN=4 (high = idle)

    os.environ['PETREL_KLIPPER_INPUT'] = link
    from gpiozero import Device, Button
    from petrel.hardware.klipper_input import pin_factory
    Device.pin_factory = pin_factory((A, B, BTN))
    from encoder import Encoder
    enc = Encoder(A, B)
    btn = Button(BTN, pull_up=True, bounce_time=0.05, hold_time=0.3,
                 hold_repeat=False)
    presses = []
    btn.when_pressed = lambda: presses.append('p')
    btn.when_held = lambda: presses.append('h')

    time.sleep(0.3)
    assert presses == [], presses   # backlog click discarded

    # One full quadrature cycle each way (A leads B = one direction).
    def turn(seq):
        for s in seq:
            os.write(master, str(s | 4).encode())
            time.sleep(0.02)
    cw = [3, 2, 0, 1, 3]
    ccw = [3, 1, 0, 2, 3]
    turn(cw)
    assert wait_for(lambda: enc.getValue() != 0), 'no rotation seen'
    first = enc.getValue()
    turn(ccw)
    assert wait_for(lambda: enc.getValue() == 0), enc.getValue()

    # Click, then hold.
    os.write(master, b'3')
    time.sleep(0.1)
    os.write(master, b'7')
    assert wait_for(lambda: presses == ['p']), presses
    time.sleep(0.1)
    os.write(master, b'3')
    assert wait_for(lambda: presses == ['p', 'p', 'h']), presses
    os.write(master, b'7')
    print('ok: first turn -> %+d, back to 0, click, hold' % first)

    # Buzzer goes back over the same pty to Klipper's beeper pin.
    from buzzer_pwm import HardwarePWM
    beeper = HardwarePWM()
    beeper.tone(2000, 50)
    beeper.off()
    time.sleep(0.05)
    assert os.read(master, 256) == b'B2000 0.2500\nB0 0.0000\n'
    print('ok: beeper lines')


if __name__ == '__main__':
    main()
